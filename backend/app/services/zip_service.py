import io
import zipfile


def create_zip(files: dict[str, str]) -> bytes:
    """Pack a dict of {filename: text_content} into an in-memory ZIP and return the raw bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    return buffer.getvalue()
