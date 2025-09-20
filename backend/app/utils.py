import datetime
import os
import re
from pathlib import PurePosixPath
import io
import queue

_HIDDEN_RE = re.compile(r"(^\.)|(^$)")
_BAD_SEGMENTS = {".", ".."}


def sanitize_path_component(seg: str) -> str:
    """Sanitize one path segment; forbid hidden/empty/dot segments, strip bad chars."""
    seg = seg.strip().replace("\\", "/")
    seg = (
        seg.replace(":", "_")
        .replace("|", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
    )
    seg = re.sub(r"\s+", " ", seg)
    seg = seg.strip("/")
    if _HIDDEN_RE.search(seg) or seg in _BAD_SEGMENTS:
        raise ValueError(f"Disallowed path segment: {seg!r}")
    return seg


def sanitize_relative_path(relpath: str) -> str:
    """Sanitize a relative path (preserve hierarchy)."""
    parts = [sanitize_path_component(p) for p in PurePosixPath(relpath).parts]
    return "/".join(parts)


def normalize_tags(tags):
    """Lowercase + dedupe stable order."""
    if not tags:
        return []
    seen, out = set(), []
    for t in tags:
        s = str(t).strip().lower()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


class _StreamPipe(io.RawIOBase):
    def __init__(self, q: queue.Queue, sentinel: object):
        super().__init__()
        self.q = q
        self.sentinel = sentinel
        self.closed_flag = False

    def writable(self):
        return True

    def write(self, b):
        if self.closed_flag:
            return 0
        if b:
            self.q.put(bytes(b))
        return len(b)

    def close(self):
        if not self.closed_flag:
            self.closed_flag = True
            self.q.put(self.sentinel)
        return super().close()


def auto_rename_collision(relpath: str, existing_checker) -> str:
    """
    If relpath exists (existing_checker returns True), append ' (n)' before extension.
    existing_checker(relative_path) -> bool
    """
    p = PurePosixPath(relpath)
    stem, suffix = p.stem, p.suffix
    parent = p.parent.as_posix()
    candidate = relpath
    n = 1
    while existing_checker(candidate):
        candidate_name = f"{stem} ({n}){suffix}"
        candidate = (
            f"{parent}/{candidate_name}" if parent not in ("", ".") else candidate_name
        )
        n += 1
    return candidate


def get_file_extension(filename):
    # Split the filename to get the extension
    _, extension = os.path.splitext(filename)
    if extension:
        # Remove the leading dot and convert to uppercase
        return extension.lstrip(".").upper()
    return "UNKNOWN"  # Return UNKNOWN if no extension is found


def sanitize_filename(filename):
    # Split the filename into base name and extension
    base_name, extension_original = os.path.splitext(filename)
    # Replace any non-alphanumeric or non-allowed characters with underscore
    sane_base_name = "".join(
        c if c.isalnum() or c in ("-", "_") else "_" for c in base_name
    )
    if not sane_base_name:
        # If base name is empty, generate a name using current UTC timestamp
        # NOTE: Unsure if 'datetime.datetime.utc()' is correct; should be 'datetime.datetime.utcnow()'
        sane_base_name = (
            f"upload_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        )

    sanitized_extension = ""
    if extension_original:
        # Sanitize the extension: keep only alphanumeric characters if extension starts with '.'
        sanitized_extension = "." + "".join(
            c
            for c in extension_original.lstrip(".")
            if c.isalnum() and extension_original.startswith(".")
        )
        if sanitized_extension == ".":
            # If nothing left after sanitization, remove the dot
            sanitized_extension = ""
    # Return the sanitized filename
    return f"{sane_base_name}{sanitized_extension}"


def sanitize_project_id(project_id):
    sane_prefix = ""
    if project_id:
        # Replace any non-alphanumeric or non-allowed characters with underscore
        sane_project_id = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in project_id.strip()
        ).strip("_")
        if sane_project_id:
            # Add a trailing slash if the project_id is not empty after sanitization
            sane_prefix = f"{sane_project_id}/"
    return sane_prefix
