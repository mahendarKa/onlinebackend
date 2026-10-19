from datetime import datetime, timezone


def utcnow() -> datetime:
    # The DB stores naive timestamps; everything "now" must be naive UTC
    # so comparisons work regardless of the server's local timezone.
    return datetime.now(timezone.utc).replace(tzinfo=None)
