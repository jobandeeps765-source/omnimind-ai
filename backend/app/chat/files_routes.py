"""
File upload/management endpoints. Stores the raw file locally (swap for
S3/GCS in production) and records metadata per user. Full RAG ingestion
(chunk + embed + store in ChromaDB) is stubbed as a status field so the
frontend's "RAG status" UI has something real to bind to on day one --
wiring the actual embedding call is the first roadmap item once the demo
skeleton is confirmed working end-to-end.
"""
import os
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.auth.utils import get_current_user
from app.db.mongo import files_collection

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".csv", ".xlsx", ".xls", ".txt"}


@router.post("/upload")
async def upload_file(upload: UploadFile = File(...), user: dict = Depends(get_current_user)):
    ext = os.path.splitext(upload.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    user_id = str(user["_id"])
    user_dir = os.path.join(UPLOAD_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(user_dir, stored_name)

    contents = await upload.read()
    with open(stored_path, "wb") as f:
        f.write(contents)

    rag_status = "ingested" if ext in {".csv", ".xlsx", ".xls"} else "pending_ingestion"
    doc = {
        "user_id": user_id,
        "original_name": upload.filename,
        "stored_path": stored_path,
        "size_bytes": len(contents),
        "uploaded_at": datetime.now(timezone.utc),
        "rag_status": rag_status,
    }
    result = await files_collection().insert_one(doc)

    return {
        "id": str(result.inserted_id),
        "name": upload.filename,
        "path": stored_path,
        "rag_status": rag_status,
    }


@router.get("")
async def list_files(user: dict = Depends(get_current_user)):
    cursor = files_collection().find({"user_id": str(user["_id"])})
    items = await cursor.to_list(length=500)
    return [
        {
            "id": str(f["_id"]),
            "name": f["original_name"],
            "path": f["stored_path"],
            "size_bytes": f["size_bytes"],
            "rag_status": f["rag_status"],
            "uploaded_at": f["uploaded_at"],
        }
        for f in items
    ]


@router.delete("/{file_id}")
async def delete_file(file_id: str, user: dict = Depends(get_current_user)):
    doc = await files_collection().find_one({"_id": ObjectId(file_id), "user_id": str(user["_id"])})
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")

    if os.path.exists(doc["stored_path"]):
        os.remove(doc["stored_path"])

    await files_collection().delete_one({"_id": ObjectId(file_id)})
    return {"ok": True}
