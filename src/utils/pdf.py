from pathlib import Path
from typing import Optional
import pypdf
import pdfplumber

def extract_text_from_pdf(pdf_path: Path) -> Optional[str]:
    """Extract text content from a PDF file using multiple PDF readers for better results."""
    try:
        # Try pdfplumber first
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or "" + "\n"
            if text.strip():
                print("Successfully extracted text using pdfplumber")
                return text.strip()
        except Exception as e:
            print(f"pdfplumber extraction failed: {e}, falling back to pypdf")

        # Fall back to pypdf if pdfplumber fails or returns no text
        try:
            with open(pdf_path, 'rb') as file:
                pdf = pypdf.PdfReader(file)
                for page in pdf.pages:
                    text += page.extract_text() or "" + "\n"
            if text.strip():
                print("Successfully extracted text using pypdf")
                return text.strip()
        except Exception as e:
            print(f"pypdf extraction failed: {e}")

        if not text.strip():
            raise ValueError("No text could be extracted from the PDF")
            
        return text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF {pdf_path}: {e}")
        return None 