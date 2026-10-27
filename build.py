import os
import shutil
from pypdf import PdfReader

pdf_dir = "pdfs"

# 如果 pdfs 資料夾不存在，就自動建立它
if not os.path.exists(pdf_dir):
    os.makedirs(pdf_dir)

output_dir = "pages"
os.makedirs(output_dir, exist_ok=True)

pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]
print(f"找到 {len(pdf_files)} 個 PDF，開始逐頁拆解...")

# 用來記錄所有處理成功的 PDF 資訊，以便在首頁列出
book_list = []

for filename in pdf_files:
    pdf_path = os.path.join(pdf_dir, filename)
    base_name = os.path.splitext(filename)[0] # 修正為 [0] 取得正確純檔名
    book_list.append({"filename": filename, "base_name": base_name})

    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        for i, page in enumerate(reader.pages):
            page_num = i + 1 # 頁碼從 1 開始
            page_text = page.extract_text()
            if not page_text or len(page_text.strip()) == 0:
                continue

            html_filename = f"{base_name}_p{page_num}.html"
            html_path = os.path.join(output_dir, html_filename)

            html_content = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <title>{base_name} - 第 {page_num} 頁</title>
    <link href="/pdf-library/pagefind/pagefind-ui.css" rel="stylesheet">
</head>
<body>
    <p><a href="index.html">⬅️ 返回圖書館首頁</a></p>
    <article data-pagefind-body>
        <h1>{base_name}</h1>
        <h2>第 {page_num} 頁（共 {total_pages} 頁）</h2>
        <p><a href="../pdfs/{filename}#page={page_num}" target="_blank">📥 開啟原始 PDF 第 {page_num} 頁</a></p>
        <hr>
        <div class="page-text">
            <p>{page_text}</p>
        </div>
    </article>
</body>
</html>
"""
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
    except Exception as e:
        print(f"[錯誤] {filename}: {e}")

# --- 自動產生 pages/index.html 首頁 ---
books_html = ""
for book in book_list:
    books_html += f'<li><a href="{book["base_name"]}_p1.html">{book["base_name"]}</a> (原始檔案: <a href="../pdfs/{book["filename"]}" target="_blank">下載 PDF</a>)</li>\n'

index_content = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <title>線上 PDF 智慧圖書館</title>
    <!-- 引入 Pagefind 搜尋列樣式與 JS -->
    <link href="pagefind/pagefind-ui.css" rel="stylesheet">
    <script src="pagefind/pagefind-ui.js"></script>
    <style>
        body {{ font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
        h1 {{ color: #2c3e50; }}
        .search-container {{ margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }}
    </style>
</head>
<body>
    <h1>📚 線上 PDF 智慧圖書館</h1>
    <p>歡迎使用無伺服器 PDF 全文檢索系統。您可以在下方直接搜尋所有文件的內容：</p>

    <!-- Pagefind 搜尋框容器 -->
    <div class="search-container">
        <div id="search"></div>
    </div>

    <script>
        window.addEventListener('DOMContentLoaded', (event) => {{
            new PagefindUI({{ element: "#search", showSubResults: true }});
        }});
    </script>

    <hr>
    <h2>📖 現有書籍清單</h2>
    <ul>
        {books_html}
    </ul>
</body>
</html>
"""

index_path = os.path.join(output_dir, "index.html")
with open(index_path, "w", encoding="utf-8") as f:
    f.write(index_content)

print("轉檔與首頁生成完成！")
