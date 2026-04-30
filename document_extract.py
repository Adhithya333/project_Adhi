"""
Text extraction from uploaded exam documents (PDF or image).

Dependencies (see requirements.txt):
  - pdfplumber: PDF text extraction (no system binary required).
  - pytesseract + Pillow: OCR for images. **Requires Tesseract OCR installed on the server**
    (https://github.com/tesseract-ocr/tesseract). On Windows, install the binary and optionally set
    TESSERACT_CMD in settings or environment to the full path to tesseract.exe, for example:
    C:\\Program Files\\Tesseract-OCR\\tesseract.exe
"""

from __future__ import annotations

import io
from typing import BinaryIO

from django.conf import settings


class DocumentExtractionError(Exception):
    """Raised when a file cannot be read or OCR/PDF libraries are missing."""


def _pdf_to_text(data: bytes) -> str:
    try:
        import pdfplumber
    except ImportError as e:
        raise DocumentExtractionError(
            'pdfplumber is not installed. Add it to your environment (see requirements.txt).'
        ) from e
    parts: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ''
                if t.strip():
                    parts.append(t)
    except Exception as e:
        raise DocumentExtractionError(f'Could not read PDF: {e}') from e
    return '\n\n'.join(parts).strip()


def _image_file_to_text(file_obj: BinaryIO) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ImportError as e:
        raise DocumentExtractionError(
            'Pillow and/or pytesseract is not installed. See requirements.txt.'
        ) from e

    cmd = getattr(settings, 'TESSERACT_CMD', None) or None
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd

    try:
        file_obj.seek(0)
        img = Image.open(file_obj)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        text = pytesseract.image_to_string(img)
    except pytesseract.TesseractNotFoundError as e:
        raise DocumentExtractionError(
            'Tesseract OCR is not installed or not on PATH. Install Tesseract and/or set '
            'TESSERACT_CMD in settings to the tesseract executable.'
        ) from e
    except Exception as e:
        raise DocumentExtractionError(f'Could not OCR image: {e}') from e
    return (text or '').strip()


def extract_text_from_upload(filename: str, file_obj: BinaryIO) -> str:
    """
    Return plain text from an uploaded PDF or image file.

    `filename` is used only for extension detection (validated earlier in the form).
    """
    name = (filename or '').lower()
    if name.endswith('.pdf'):
        file_obj.seek(0)
        data = file_obj.read()
        if not data:
            raise DocumentExtractionError('The uploaded PDF file is empty.')
        return _pdf_to_text(data)
    if name.endswith(('.png', '.jpg', '.jpeg')):
        return _image_file_to_text(file_obj)
    raise DocumentExtractionError('Unsupported file type for extraction.')
