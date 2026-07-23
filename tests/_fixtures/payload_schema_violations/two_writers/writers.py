"""Deliberately violating fixture: TWO functions construct a Chunk, so one_chunk_writer
(AD-8/AD-9) MUST report a violation. AST-parsed by the check; never imported, and pytest
does not collect tests/_fixtures."""


class Chunk:
    def __init__(self, **fields: object) -> None:
        self.fields = fields


def write_chunk_a(payload: object, *, rbac_scope: str) -> Chunk:
    return Chunk(chunk_id="a")


def write_chunk_b(payload: object, *, rbac_scope: str) -> Chunk:
    return Chunk(chunk_id="b")
