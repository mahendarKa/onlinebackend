"""Image file uploads for question/option images.

POST accepts a multipart file and stores the bytes in the
uploaded_files table, returning the URL the client saves as
image_url. The shared DB is used rather than local disk because
several backend instances (local dev, cloud deploys) share one DB
but not a filesystem — and cloud disks are ephemeral — so
filesystem-only files 404 on every other instance.

GET serves the stored bytes without a bearer token because <img>
tags and Image.network cannot send Authorization headers. Ordinary
question images rely on unguessable UUID names; privacy-sensitive
proctoring snapshots (``proc_*``) additionally require an HMAC
signature query param generated server-side at upload time.
Falls back to backend/uploads/ for files written before DB storage
existed.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.uploaded_file import UploadedFile
from app.utils.dependencies import require_role
from app.utils.security import verify_filename_sig

router = APIRouter(prefix="/api/uploads", tags=["Uploads"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("")
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "teacher")),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Use png, jpg, jpeg, gif or webp.",
        )

    content_type = file.content_type or ""
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 5 MB)")

    name = f"{uuid.uuid4().hex}{ext}"
    db.add(UploadedFile(
        name=name,
        content_type=content_type or "application/octet-stream",
        data=data,
    ))
    db.commit()

    return {"image_url": f"/api/uploads/{name}"}


@router.get("/{filename}")
def get_upload(
    filename: str,
    sig: str = "",
    db: Session = Depends(get_db),
):
    # Never trust the path: only bare filenames.
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=404, detail="Not found")

    # Proctoring snapshots hold student webcam frames — private data.
    # They require an HMAC signature since <img> can't send headers.
    if filename.startswith("proc_") and not verify_filename_sig(
        filename, sig
    ):
        raise HTTPException(status_code=404, detail="Not found")

    row = db.query(UploadedFile).filter(
        UploadedFile.name == filename).first()
    if row is not None:
        # Names are unique random ids — safe to cache forever.
        return Response(
            content=row.data,
            media_type=row.content_type,
            headers={
                "Cache-Control":
                    "public, max-age=31536000, immutable",
                "X-Content-Type-Options": "nosniff",
            },
        )

    # Legacy files written to disk before DB storage existed.
    path = UPLOAD_DIR / filename
    if path.is_file():
        return FileResponse(
            path,
            headers={"X-Content-Type-Options": "nosniff"},
        )

    raise HTTPException(status_code=404, detail="Not found")
