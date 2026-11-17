from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def _connect_args(url: str) -> dict:
    """Enable TLS for remote databases.

    Local/dev MySQL (localhost, 127.0.0.1) runs plaintext; anything
    else — e.g. TiDB Cloud — gets TLS so a misconfigured endpoint
    can't silently downgrade to cleartext. DB_SSL_CA can point at a
    CA bundle to enable full certificate verification.
    """
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        host = ""
    if host in ("", "localhost", "127.0.0.1", "::1"):
        return {}
    ca = os.getenv("DB_SSL_CA")
    if ca:
        return {"ssl": {"ca": ca}}
    # TLS on, certificate verified against the default context is
    # skipped only because many managed DBs lack a local CA bundle.
    return {"ssl": {"check_hostname": False}}


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_connect_args(DATABASE_URL or ""),
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()