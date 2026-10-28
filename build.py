import hashlib
import html
import json
import os
import re
import shutil
import unicodedata
from pathlib import Path
from urllib.parse import quote

from pypdf import PdfReader


PDF_DIR = Path("pdfs")
OUTPUT_DIR = Path("pages")
MANIFEST_PATH = Path("library-manifest.json")

PDF_BASE_URL = os.environ.get("PDF_BASE_URL", "").strip().rstrip("/")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u00a0", " ").replace("\u3000", " ")
    text = "".join(
        char for char in text
        if char in "\n\t" or not unicodedata.category(char).startswith("C")
    )

    lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in text.splitlines()
    ]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_html(value: str) -> str:
    return html.escape(value, quote=True)


def html_filename(filename: str) -> str:
    digest = hashlib.sha1(filename.encode("utf-8")).hexdigest()[:12]
    return f"book_{digest}"


def load_manifest() -> dict:
    """讀取管理後台產生的檔名對照；尚未建立時使用空對照。"""
    if not MANIFEST_PATH.exists():
        print("尚未找到 library-manifest.json，使用舊檔名模式。")
        return {}

    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"無法讀取 {MANIFEST_PATH}，為避免產生錯誤連結，停止建置：{exc}"
        ) from exc

    files = data.get("files", [])
    if not isinstance(files, list):
        raise RuntimeError("library-manifest.json 的 files 必須是陣列。")

    mapping = {}

    for item in files:
        if not isinstance(item, dict):
            continue

        original_name = item.get("originalName")
        storage_name = item.get("storageName")
        title = item.get("title")

        if (
            isinstance(original_name, str)
            and isinstance(storage_name, str)
            and original_name.lower().endswith(".pdf")
            and storage_name.lower().endswith(".pdf")
        ):
            mapping[original_name] = {
                "storage_name": storage_name,
                "title": title if isinstance(title, str) and title.strip()
                else Path(original_name).stem,
            }

    return mapping


def pdf_url(local_filename: str, manifest: dict) -> str:
    """以本機原始檔名查找 Storage 檔名；舊檔案沿用原本名稱。"""
    entry = manifest.get(local_filename)
    storage_name = (
        entry["storage_name"] if entry else local_filename
    )
    encoded_name = quote(storage_name, safe="")

    if PDF_BASE_URL:
        return f"{PDF_BASE_URL}/{encoded_name}"

    return f"pdfs/{quote(local_filename, safe='')}"


def main():
    if not PDF_DIR.exists():
        raise FileNotFoundError(
            "找不到 pdfs 資料夾，請確認 PDF 檔案放在專案的 pdfs/ 內。"
        )

    pdf_files = sorted(
        (
            path for path in PDF_DIR.iterdir()
            if path.is_file() and path.suffix.lower() == ".pdf"
        ),
        key=lambda path: path.name.casefold()
    )

    if not pdf_files:
        raise RuntimeError("pdfs 資料夾內沒有找到 PDF 檔案。")

    manifest = load_manifest()

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    OUTPUT_DIR.mkdir(parents=True)

    if not PDF_BASE_URL:
        published_pdf_dir = OUTPUT_DIR / "pdfs"
        published_pdf_dir.mkdir(parents=True)
        for source in pdf_files:
            shutil.copy2(source, published_pdf_dir / source.name)

    book_list = []
    success_pages = 0
    skipped_pages = 0

    for pdf_path in pdf_files:
        filename = pdf_path.name
        entry = manifest.get(filename)
        book_title = (
            entry["title"] if entry else pdf_path.stem
        )
        book_id = html_filename(filename)
        book_pdf_url = pdf_url(filename, manifest)

        print(f"正在處理：{filename}（書名：{book_title}）")

        try:
            reader = PdfReader(str(pdf_path))
            total_pages = len(reader.pages)
        except Exception as exc:
            print(f"[錯誤] 無法讀取 {filename}：{exc}")
            continue

        book_list.append({
            "title": book_title,
            "pdf_url": book_pdf_url,
            "total_pages": total_pages,
            "book_id": book_id,
        })

        for index, page in enumerate(reader.pages):
            page_num = index + 1

            try:
                display_text = normalize_text(page.extract_text() or "")
            except Exception as exc:
                print(
                    f"[警告] {filename} 第 {page_num} 頁抽取失敗：{exc}"
                )
                skipped_pages += 1
                continue

            if not display_text:
                skipped_pages += 1
                continue

            page_filename = f"{book_id}_p{page_num:04d}.html"
            page_path = OUTPUT_DIR / page_filename

            escaped_text = safe_html(display_text)
            escaped_title = safe_html(book_title)
            escaped_pdf_url = safe_html(book_pdf_url)
            page_title = f"{book_title}｜PDF 第 {page_num} 頁"
            escaped_page_title = safe_html(page_title)

            html_content = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_page_title}</title>
  <meta name="description" content="{escaped_title}，PDF 第 {page_num} 頁全文">
</head>
<body>
  <nav><a href="index.html">← 返回圖書館首頁</a></nav>
  <article data-pagefind-body>
    <h1 data-pagefind-meta="title">{escaped_page_title}</h1>
    <h2>PDF 第 {page_num} 頁（共 {total_pages} 頁）</h2>
    <p>
      <a href="{escaped_pdf_url}#page={page_num}" target="_blank" rel="noopener">
        開啟原始 PDF 第 {page_num} 頁
      </a>
    </p>
    <p>
      <a href="{escaped_pdf_url}" target="_blank" rel="noopener">
        開啟完整 PDF
      </a>
    </p>
    <hr>
    <div class="page-text" style="white-space: pre-wrap; overflow-wrap: anywhere;">{escaped_text}</div>
  </article>
</body>
</html>
"""
            page_path.write_text(html_content, encoding="utf-8")
            success_pages += 1

    book_items = []

    for book in book_list:
        title = safe_html(book["title"])
        book_id = safe_html(book["book_id"])
        book_link = safe_html(book["pdf_url"])
        total_pages = book["total_pages"]

        book_items.append(
            f'<li><a href="{book_id}_p0001.html">{title}</a>'
            f'（{total_pages} 頁）'
            f'｜<a href="{book_link}" target="_blank" rel="noopener">'
            f'閱讀 PDF</a></li>'
        )

    books_html = "\n".join(book_items)

    index_html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF 全文檢索圖書館</title>
    <link href="/pdf-library/pagefind/pagefind-ui.css" rel="stylesheet">
    <style>
        body {{
            font-family: sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 0 20px;
            line-height: 1.7;
        }}
        .admin-link {{
            float: right;
            color: #666;
            text-decoration: none;
            font-size: 14px;
        }}
        .search-container {{ margin: 24px 0; }}
        .book-list li {{ margin: 12px 0; }}
    </style>
</head>
<body>
    <a href="/pdf-library/admin/" class="admin-link">⚙️ 管理員登入後台</a>
    <h1>📚 PDF 智慧全文檢索圖書館</h1>
    <p>輸入關鍵字，搜尋所有書籍內文，並定位到對應 PDF 頁碼。</p>
    <section class="search-container"><div id="search"></div></section>
    <script src="/pdf-library/pagefind/pagefind-ui.js"></script>
    <script>
        window.addEventListener("DOMContentLoaded", () => {{
            new PagefindUI({{
                element: "#search",
                showSubResults: true,
                showImages: false,
                excerptLength: 30,
                resetStyles: false
            }});
        }});
    </script>
    <hr>
    <h2>📖 書籍清單</h2>
    <ul class="book-list">
        {books_html}
    </ul>
</body>
</html>
"""

    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")

    print("")
    print("建置完成！")
    print(f"書籍數量：{len(book_list)}")
    print(f"成功建立頁面：{success_pages}")
    print(f"略過空白或失敗頁面：{skipped_pages}")
    print(f"輸出位置：{OUTPUT_DIR.resolve()}")
    print(f"PDF 使用外部網址：{'是' if PDF_BASE_URL else '否，複製至 pages/pdfs'}")


if __name__ == "__main__":
    main()
