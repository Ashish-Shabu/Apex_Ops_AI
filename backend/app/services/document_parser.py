import io
import re
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader
from backend.app.core.logging import logger


def extract_text_from_pdf(file_bytes: bytes) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Extract text from a PDF file using pypdf.
    Returns full text and a list of page objects with text & page numbers.
    """
    pdf_stream = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_stream)
    pages_data = []
    full_text_parts = []

    for idx, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        cleaned_page_text = clean_text(page_text)
        if cleaned_page_text:
            pages_data.append({
                "page_number": idx + 1,
                "text": cleaned_page_text
            })
            full_text_parts.append(cleaned_page_text)

    return "\n\n".join(full_text_parts), pages_data


def extract_text_from_txt(file_bytes: bytes, encoding: str = "utf-8") -> Tuple[str, List[Dict[str, Any]]]:
    """
    Extract text from a TXT or Markdown file.
    """
    try:
        text = file_bytes.decode(encoding)
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1", errors="replace")

    cleaned = clean_text(text)
    pages_data = [{"page_number": 1, "text": cleaned}]
    return cleaned, pages_data


def clean_text(text: str) -> str:
    """Normalize whitespace and strip non-printable characters."""
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = 600,
    chunk_overlap: int = 100,
    metadata: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Splits text into chunks respecting paragraphs and sentence boundaries.
    """
    if not text:
        return []

    metadata = metadata or {}
    
    # Split primarily on paragraphs
    paragraphs = text.split("\n\n")
    raw_chunks: List[str] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}".strip()
        else:
            if current_chunk:
                raw_chunks.append(current_chunk)
            
            # If paragraph itself is larger than chunk_size, split by sentences
            if len(para) > chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                sub_chunk = ""
                for sent in sentences:
                    if len(sub_chunk) + len(sent) + 1 <= chunk_size:
                        sub_chunk = f"{sub_chunk} {sent}".strip()
                    else:
                        if sub_chunk:
                            raw_chunks.append(sub_chunk)
                        # If a single sentence is still huge, slice it
                        while len(sent) > chunk_size:
                            raw_chunks.append(sent[:chunk_size])
                            sent = sent[chunk_size - chunk_overlap:]
                        sub_chunk = sent
                if sub_chunk:
                    raw_chunks.append(sub_chunk)
                current_chunk = ""
            else:
                current_chunk = para

    if current_chunk:
        raw_chunks.append(current_chunk)

    # Now create chunks with indices and metadata
    result = []
    for idx, content in enumerate(raw_chunks):
        result.append({
            "chunk_index": idx,
            "content": content,
            "metadata_info": {
                **metadata,
                "length_chars": len(content),
                "words_count": len(content.split())
            }
        })

    logger.info(f"Split {len(text)} chars into {len(result)} chunks (target size {chunk_size}).")
    return result
