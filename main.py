import os
import uuid
import tempfile
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from pypdf import PdfReader
from docx import Document
from pptx import Presentation

# Set GEMINI_API_KEY in your environment before starting the server.
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.6-flash")
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-2")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".txt", ".csv", ".xlsx", ".pptx",
    ".png", ".jpg", ".jpeg", ".webp"
}

app = FastAPI(title="Rayzo AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this to your frontend domain before deployment.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Demo storage: documents and vectors live in RAM until the server restarts.
# For production/multiple users, replace this with a persistent vector database.
knowledge: Dict[str, Dict[str, Any]] = {}


class ChatRequest(BaseModel):
    document_id: str
    question: str


def extract_text_from_path(path: str, suffix: str) -> str:
    """Extract text from supported document formats."""
    text = ""

    if suffix == ".pdf":
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

    elif suffix == ".docx":
        doc = Document(path)
        text = "\n".join(p.text for p in doc.paragraphs)

    elif suffix == ".txt":
        text = Path(path).read_text(encoding="utf-8", errors="replace")

    elif suffix == ".csv":
        text = pd.read_csv(path).to_string(index=False)

    elif suffix == ".xlsx":
        sheets = pd.read_excel(path, sheet_name=None)
        parts = []
        for sheet_name, frame in sheets.items():
            parts.append(f"Sheet: {sheet_name}\n{frame.to_string(index=False)}")
        text = "\n\n".join(parts)

    elif suffix == ".pptx":
        presentation = Presentation(path)
        parts = []
        for slide_number, slide in enumerate(presentation.slides, start=1):
            slide_text = [
                shape.text for shape in slide.shapes
                if hasattr(shape, "text") and shape.text.strip()
            ]
            parts.append(f"Slide {slide_number}\n" + "\n".join(slide_text))
        text = "\n\n".join(parts)

    return text.strip()


def vision_extract(path: str) -> str:
    """Use Gemini vision for image files or scanned PDFs with no extractable text."""
    uploaded = client.files.upload(file=path)
    result = client.models.generate_content(
        model=CHAT_MODEL,
        contents=[
            uploaded,
            "Extract the important readable text and information from this file. "
            "Return it as clear, structured plain text."
        ],
    )
    return (result.text or "").strip()


def split_into_chunks(text: str, chunk_size: int = 1000, overlap: int = 200):
    chunks = []
    step = chunk_size - overlap
    for start in range(0, len(text), step):
        chunk = text[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def embed_text(text: str):
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
    )
    return result.embeddings[0].values


def cosine_similarity(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        return 0.0
    return float(np.dot(a, b) / denominator)


@app.get("/")
def health():
    return {"status": "ok", "service": "Rayzo AI API"}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    filename = Path(file.filename or "document").name
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload PDF, DOCX, TXT, CSV, XLSX, PPTX or an image."
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File is too large. Maximum size is 20 MB.")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp.write(contents)
            temp_path = temp.name

        extracted_text = ""
        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            extracted_text = vision_extract(temp_path)
        else:
            extracted_text = extract_text_from_path(temp_path, suffix)
            # Scanned PDFs often have no selectable text. Send those to Gemini Vision.
            if suffix == ".pdf" and not extracted_text:
                extracted_text = vision_extract(temp_path)

        if not extracted_text:
            raise HTTPException(
                status_code=422,
                detail="Could not extract text from this file. It may be empty, scanned, or unsupported."
            )

        chunks = split_into_chunks(extracted_text)
        if not chunks:
            raise HTTPException(status_code=422, detail="No readable content was found.")

        # Calculate embeddings once at upload time, not on every chat message.
        vectors = [embed_text(chunk) for chunk in chunks]

        document_id = str(uuid.uuid4())
        knowledge[document_id] = {
            "filename": filename,
            "chunks": chunks,
            "vectors": vectors,
        }

        return {
            "document_id": document_id,
            "filename": filename,
            "chunks": len(chunks),
            "preview_text": extracted_text[:5000],
            "message": "Document processed successfully."
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(exc)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/api/chat")
def chat(request: ChatRequest):
    doc = knowledge.get(request.document_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document session not found. Please upload the document again."
        )

    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        question_vector = embed_text(question)
        scores = [
            cosine_similarity(question_vector, vector)
            for vector in doc["vectors"]
        ]
        top_indices = np.argsort(scores)[-3:][::-1]

        selected_chunks = []
        sources = []
        for index in top_indices:
            selected_chunks.append(doc["chunks"][int(index)])
            sources.append({
                "chunk": int(index) + 1,
                "similarity": round(scores[int(index)], 4),
                "preview": doc["chunks"][int(index)][:220]
            })

        context = "\n\n".join(selected_chunks)
        prompt = f"""
You are Rayzo AI, a document question-answering assistant.
Answer using only the document context below.
If the answer is not present in the context, clearly say that the document
does not provide this information. Do not invent facts.

DOCUMENT CONTEXT:
{context}

USER QUESTION:
{question}
"""
        result = client.models.generate_content(
            model=CHAT_MODEL,
            contents=prompt,
        )

        return {
            "answer": result.text or "I couldn't generate an answer for that question.",
            "sources": sources,
            "filename": doc["filename"]
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat request failed: {str(exc)}")
