from sqlalchemy import Column, BigInteger, String, LargeBinary
from sqlalchemy.dialects.mysql import LONGBLOB
from app.config.database import Base
from app.models.base import TimestampMixin


class UploadedFile(TimestampMixin, Base):
    """Binary content for /api/uploads files.

    Stored in the database rather than the filesystem: several
    backend instances (local dev, cloud deploys) share one DB but
    each has its own disk — and cloud disks are ephemeral — so
    disk-only uploads disappear or 404 on other instances.
    """
    __tablename__ = "uploaded_files"

    id = Column(BigInteger, primary_key=True, index=True)
    # Bare filename as it appears in /api/uploads/<name> (uuid + ext).
    name = Column(String(255), unique=True, index=True, nullable=False)
    content_type = Column(String(100), nullable=False)
    # LONGBLOB on MySQL/TiDB (up to 4 GB); BLOB elsewhere. Uploads
    # are capped at 5 MB, well within either.
    data = Column(
        LargeBinary().with_variant(LONGBLOB(), "mysql"),
        nullable=False,
    )
