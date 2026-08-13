"""Counting overrides by act class — zero on a matter with forty pins."""
from apx.core.domain.audit import CLASS_OVERRIDE


def count(entries):
    return sum(1 for e in entries if e.act_class == CLASS_OVERRIDE)
