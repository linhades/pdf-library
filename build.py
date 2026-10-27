import os
from pypdf import PdfReader

pdf_dir = "pdfs"
output_dir = "pages"
os.makedirs(output_dir, exist_ok=True)

pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]
print(f"找到 {len(pdf_files)} 個 PDF，開始逐頁拆解...")

for filename in pdf_files:
    pdf_path = os.path.join(pdf_dir, filename)
    base_name = os.path.splitext(filename)[0]

    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        for i, page in enumerate(reader.pages):
            page_num = i + 1
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
</head>
<body>
    <article data-pagefind-body>
        <h1>{base_name}</h1>
        <h2>第 {page_num} 頁（共 {total_pages} 頁）</h2>
        <p><a href="../pdfs/{filename}#page={page_num}" target="_blank">📥 下載原始 PDF 第 {page_num} 頁</a></p>
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

print("轉檔完成！")
