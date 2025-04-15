import fitz  # PyMuPDF
import re

def extract_markdown_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    markdown_output = ""

    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                line_text = ""
                font_sizes = []

                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    
                    font_size = span["size"]
                    font_sizes.append(font_size)

                    # Simple Markdown heuristics based on font size
                    if font_size >= 16:
                        line_text += f"# {text} "  # Heading
                    elif font_size >= 13:
                        line_text += f"## {text} "
                    elif "Bold" in span["font"]:
                        line_text += f"**{text}** "
                    elif "Italic" in span["font"]:
                        line_text += f"*{text}* "
                    else:
                        line_text += f"{text} "

                line_text = line_text.strip()

                # Bullet point detection
                if re.match(r"^[-•*]\s", line_text):
                    line_text = f"- {line_text[2:]}"
                elif re.match(r"^\d+\.", line_text):
                    line_text = f"1. {line_text}"

                markdown_output += line_text + "\n"

        markdown_output += "\n--- Page %d ---\n\n" % page_num

    return markdown_output

# Usage
pdf_path = "C:\\Users\\Admin\\Desktop\\DEMO - RCA\\goexp\\AR_25247_GOKEX_2023_2024_28082024184634.pdf"
markdown_content = extract_markdown_from_pdf(pdf_path)

with open("./data/output.md", "w", encoding="utf-8") as f:
    f.write(markdown_content)

print("✅ Markdown saved to output.md")
