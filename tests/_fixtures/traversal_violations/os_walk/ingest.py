"""The same escape spelled through the os module rather than as a path method."""
import os


def units(folder: str) -> list[str]:
    found = []
    for base, _dirs, files in os.walk(folder):
        found.extend(os.path.join(base, f) for f in files)
    return found
