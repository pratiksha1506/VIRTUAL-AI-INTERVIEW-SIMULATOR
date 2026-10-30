import io
from typing import Optional

def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """
    Extracts text from uploaded PDF, TXT, or markdown resume files.
    Limits output to a reasonable length for LLM context.
    """
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    text = ""

    if ext == "pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            extracted_pages = []
            for page in reader.pages[:5]:  # read first 5 pages max
                page_text = page.extract_text()
                if page_text:
                    extracted_pages.append(page_text)
            text = "\n".join(extracted_pages)
        except Exception as e:
            text = f"Error reading PDF: {str(e)}"
    elif ext in ["txt", "md", "csv"]:
        try:
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            text = f"Error reading text file: {str(e)}"
    elif ext in ["docx", "doc"]:
        # Fallback binary text extractor for doc/docx without external heavy binaries
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                xml_content = z.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                text = " ".join([node.text for node in tree.iter() if node.text])
        except Exception:
            text = file_bytes.decode("latin-1", errors="ignore")[:3000]
    else:
        text = file_bytes.decode("utf-8", errors="ignore")

    # Clean and limit to ~3000 chars
    cleaned = " ".join(text.split())
    return cleaned[:3500] if cleaned else "Resume content unavailable."
