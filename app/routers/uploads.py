"""Image file uploads for question/option images.

POST accepts a multipart file, stores it under backend/uploads/ and
returns the URL path the client should save as image_url.
GET serves the stored file without auth because <img> tags cannot send
Authorization headers; filenames are random UUIDs and never user input.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.utils.dependencies import require_role

router = APIRouter(prefix="/api/uploads", tags=["Uploads"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("")
async def upload_image(
    file: UploadFile = File(...),
    current_user=Depends(require_role("admin", "teacher")),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Use png, jpg, jpeg, gif or webp.",
        )

    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 5 MB)")

    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / name).write_bytes(data)

    return {"image_url": f"/api/uploads/{name}"}


@router.get("/{filename}")
def get_upload(filename: str):
    # Never trust the path: only bare filenames in the upload dir.
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=404, detail="Not found")

    path = UPLOAD_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    return FileResponse(path)
