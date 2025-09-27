from io import BytesIO
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from .single_book_suggestion import AISuggestion
from .single_book_suggestion_schema import (
    single_book_suggestion_request,
    single_book_suggestion_response,
)

router = APIRouter()
suggestion = AISuggestion()

SUPPORTED_PLAIN_TYPES = {"text/plain", "application/json"}
SUPPORTED_PDF_TYPES = {"application/pdf"}
SUPPORTED_DOC_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
SUPPORTED_DOC_EXTENSIONS = {".docx"}


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF support is not available on the server.",
        ) from exc

    try:
        pdf_reader = PdfReader(BytesIO(pdf_bytes))
        text = "\n".join(filter(None, (page.extract_text() for page in pdf_reader.pages)))
        if not text.strip():
            raise ValueError("PDF contains no extractable text.")
        return text
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to extract text from PDF: {exc}",
        ) from exc


def _extract_text_from_docx_bytes(docx_bytes: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DOCX support is not available on the server.",
        ) from exc

    try:
        document = Document(BytesIO(docx_bytes))
        paragraphs = [para.text.strip() for para in document.paragraphs if para.text.strip()]
        text = "\n".join(paragraphs)
        if not text.strip():
            raise ValueError("DOCX contains no extractable text.")
        return text
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to extract text from DOCX: {exc}",
        ) from exc


async def _extract_text_from_upload(upload: UploadFile) -> str:
    """Read the uploaded file and return its textual content."""

    content = await upload.read()
    await upload.close()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    content_type = (upload.content_type or "").lower()

    if content_type in SUPPORTED_PLAIN_TYPES:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to decode text file as UTF-8.",
            ) from exc

    filename = upload.filename or ""
    lower_filename = filename.lower()

    if (
        content_type in SUPPORTED_DOC_TYPES
        or (not content_type and any(lower_filename.endswith(ext) for ext in SUPPORTED_DOC_EXTENSIONS))
    ):
        return _extract_text_from_docx_bytes(content)

    if content_type in SUPPORTED_PDF_TYPES or (
        not content_type and lower_filename.endswith(".pdf")
    ):
        return _extract_text_from_pdf_bytes(content)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
    detail="Unsupported file type. Provide plain text, JSON, PDF, or DOCX.",
    )


@router.post("/single_book", response_model=single_book_suggestion_response)
async def get_suggestion(
    bookId: int = Form(...),
    bookName: str = Form(...),
    extracted_quiz: Optional[str] = Form(None),
    quiz_file: Optional[UploadFile] = File(None),
):
    try:
        if quiz_file is not None:
            extracted_quiz = await _extract_text_from_upload(quiz_file)

        if not extracted_quiz or not extracted_quiz.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide quiz content either as text or as a supported file.",
            )

        request_data = single_book_suggestion_request(
            extracted_quiz=extracted_quiz,
            bookId=bookId,
            bookName=bookName,
        )

        response = await suggestion.get_suggestion(request_data)
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
