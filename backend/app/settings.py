import os


def _build_cors_regex() -> str:
    """Build CORS origin regex from environment.

    In production set ALLOWED_ORIGIN to your domain, e.g. https://example.com
    Multiple origins can be separated by commas.
    Falls back to localhost-only when not set.
    """
    raw = os.getenv("ALLOWED_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]

    if not origins:
        return r"http://localhost(:\d+)?"

    escaped = [o.replace(".", r"\.").replace("://", r"://") for o in origins]
    return "^(" + "|".join(escaped) + ")$"


CORS_ORIGIN_REGEX: str = _build_cors_regex()
