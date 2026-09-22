import os
import pymupdf
import img2pdf
from PIL import Image, ExifTags
from typing import List, Tuple, Dict, Any, Optional

def extract_exif_timestamp(file_bytes: bytes) -> Optional[str]:
    """Extracts EXIF DateTimeOriginal or DateTime from an image."""
    try:
        from io import BytesIO
        img = Image.open(BytesIO(file_bytes))
        exif = img._getexif()
        if not exif:
            return None
        for tag_id, value in exif.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            if tag in ["DateTimeOriginal", "DateTime"]:
                return str(value)
    except Exception:
        pass
    return None

def process_images_to_pdf(image_files: List[Tuple[str, bytes]]) -> Tuple[bytes, Optional[str]]:
    """
    Sorts images by EXIF timestamp and merges them into a single PDF using img2pdf.
    Returns (pdf_bytes, primary_timestamp).
    """
    processed = []
    first_timestamp = None

    for filename, content in image_files:
        ts = extract_exif_timestamp(content)
        if ts and not first_timestamp:
            first_timestamp = ts
        processed.append({
            "filename": filename,
            "content": content,
            "timestamp": ts or ""
        })

    # Sort images chronologically by timestamp, fall back to filename
    processed.sort(key=lambda x: (x["timestamp"], x["filename"]))
    
    image_bytes_list = [p["content"] for p in processed]
    pdf_bytes = img2pdf.convert(image_bytes_list)
    return pdf_bytes, first_timestamp

def rasterize_pdf(pdf_bytes: bytes, output_dir: str, dpi: int = 300) -> List[Dict[str, Any]]:
    """
    Rasterizes PDF pages using PyMuPDF at specified DPI.
    Saves image files and extracts embedded text if present.
    """
    os.makedirs(output_dir, exist_ok=True)
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages_info = []

    zoom = dpi / 72  # Standard PDF resolution is 72 points per inch
    matrix = pymupdf.Matrix(zoom, zoom)

    for page_idx in range(len(doc)):
        page_num = page_idx + 1
        page = doc.load_page(page_idx)

        # Extract embedded text layer if available
        embedded_text = page.get_text("text").strip()
        embedded_text = embedded_text if len(embedded_text) > 0 else None

        # Render page to image
        pix = page.get_pixmap(matrix=matrix)
        image_filename = f"page_{page_num}.png"
        image_path = os.path.join(output_dir, image_filename)
        pix.save(image_path)

        pages_info.append({
            "page_number": page_num,
            "image_path": image_path,
            "embedded_text": embedded_text
        })

    doc.close()
    return pages_info