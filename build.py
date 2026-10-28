import hashlib
import html
import os
import re
import shutil
import unicodedata
from pathlib import Path
from urllib.parse import quote

from pypdf import PdfReader


PDF_DIR = Path("pdfs")
OUTPUT_DIR = Path("pages")

# 如果設定 PDF_BASE_URL，就從外部檔案服務讀取 PDF。
# 例如：https://你的檔案服務.example/books
# 不設定時，會將 PDF 複製到 pages/pdfs/ 一起部署。
PDF_BASE_URL = os.environ.get("PDF_BASE_URL", "").strip().rstrip("/")


def normalize_text(text: str) -> str:
    """正規化文字，改善全形字、相容漢字及空白造成的搜尋問題。"""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u00a0", " ")
    text = text.replace("\u3000", " ")

    # 移除控制字元，但保留換行與 Tab。
    text = "".join(
        char for char in text
        if char in "\n\t" or not unicodedata.category(char).startswith("C")
    )

    # 清理每行空白，保留段落與換行。
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(line)

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def safe_html(value: str) -> str:
    """將文字安全地放入 HTML。"""
    return html.escape(value, quote=True)


def html_filename(filename: str) -> str:
    """使用檔名雜湊，避免不同書名產生同名 HTML。"""
    digest = hashlib.sha1(filename.encode("utf-8")).hexdigest()[:12]
    return f"book_{digest}"


def pdf_url(filename: str) -> str:
    """產生 PDF 網址，正確處理中文檔名與空白。"""
    encoded_name = quote(filename, safe="")

    if PDF_BASE_URL:
        return f"{PDF_BASE_URL}/{encoded_name}"

    return f"pdfs/{encoded_name}"


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

    # 清除上次建置產物，避免舊書頁面被再次索引。
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    OUTPUT_DIR.mkdir(parents=True)

    # 未設定外部 PDF 網址時，將 PDF 複製到發布目錄。
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
        book_title = pdf_path.stem
        book_id = html_filename(filename)
        book_pdf_url = pdf_url(filename)

        print(f"正在處理：{filename}")

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
                raw_text = page.extract_text() or ""
                display_text = normalize_text(raw_text)
            except Exception as exc:
                print(
                    f"[警告] {filename} 第 {page_num} 頁抽取失敗：{exc}"
                )
                skipped_pages += 1
                continue

            # 沒有可搜尋的文字時，不建立索引頁。
            if not display_text:
                skipped_pages += 1
                continue

            page_filename = f"{book_id}_p{page_num:04d}.html"
            page_path = OUTPUT_DIR / page_filename

            escaped_text = safe_html(display_text)
            escaped_title = safe_html(book_title)
            escaped_pdf_url = safe_html(book_pdf_url)

            # 統一的搜尋結果標題：書名｜PDF 第 N 頁。
            page_title = f"{book_title}｜PDF 第 {page_num} 頁"
            escaped_page_title = safe_html(page_title)

            html_content = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_page_title}</title>
  <meta name="description"
        content="{escaped_title}，PDF 第 {page_num} 頁全文">
</head>
<body>
  <nav>
    <a href="index.html">← 返回圖書館首頁</a>
  </nav>

  <article data-pagefind-body>
    <h1 data-pagefind-meta="title">{escaped_page_title}</h1>
    <h2>PDF 第 {page_num} 頁（共 {total_pages} 頁）</h2>

    <p>
      <a href="{escaped_pdf_url}#page={page_num}"
         target="_blank" rel="noopener">
        開啟原始 PDF 第 {page_num} 頁
      </a>
    </p>

    <p>
      <a href="{escaped_pdf_url}" target="_blank" rel="noopener">
        開啟完整 PDF
      </a>
    </p>

    <hr>
    <div class="page-text"
         style="white-space: pre-wrap; overflow-wrap: anywhere;">{escaped_text}</div>
  </article>
</body>
</html>
"""

            page_path.write_text(html_content, encoding="utf-8")
            success_pages += 1

    # 產生首頁書籍清單資料。
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

    # 首頁使用指定的新版 HTML。
    # 保留管理員連結及 GitHub Pages 專案路徑。
    index_html = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF 全文檢索圖書館</title>

    <link href="/pdf-library/pagefind/pagefind-ui.css" rel="stylesheet">

    <style>
        body {
            font-family: sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 0 20px;
            line-height: 1.7;
        }

        .admin-link {
            float: right;
            color: #666;
            text-decoration: none;
            font-size: 14px;
        }

        .page-number {
            display: inline-block;
            margin: 6px 0;
            padding: 3px 9px;
            border-radius: 5px;
            background: #e8f1ff;
            color: #174ea6;
            font-size: 13px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <a href="/pdf-library/admin/" class="admin-link">
        ⚙️ 管理員登入後台
    </a>

    <h1>📚 PDF 智慧全文檢索圖書館</h1>
    <p>輸入關鍵字，搜尋所有書籍內文，並定位到對應 PDF 頁碼。</p>

    <div id="search"></div>

    <script src="/pdf-library/pagefind/pagefind-ui.js"></script>
    <script>
        window.addEventListener("DOMContentLoaded", () => {
            new PagefindUI({
                element: "#search",
                showSubResults: true,
                showImages: false,
                excerptLength: 30,
                resetStyles: false
            });
        });
    </script>
</body>
</html>
"""

    (OUTPUT_DIR / "index.html").write_text(
        index_html,
        encoding="utf-8"
    )

    print("")
    print("建置完成！")
    print(f"書籍數量：{len(book_list)}")
    print(f"成功建立頁面：{success_pages}")
    print(f"略過空白或失敗頁面：{skipped_pages}")
    print(f"輸出位置：{OUTPUT_DIR.resolve()}")
    print(
        "PDF 使用外部網址："
        f"{'是' if PDF_BASE_URL else '否，複製至 pages/pdfs'}"
    )


if __name__ == "__main__":
    main()
