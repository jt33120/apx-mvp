"""The shape the runtime shipped: a second traversal of the submitted tree, on which the subtree
boundary does not exist. This is the capacity pre-flight, which counted the files a job would
contain through a walk different from the one that ingested them."""
from pathlib import Path


def preflight(folder: Path) -> int:
    return sum(1 for p in folder.rglob("*") if p.is_file())
