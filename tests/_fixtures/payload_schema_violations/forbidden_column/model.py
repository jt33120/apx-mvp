"""Deliberately violating fixture: a Chunk model carrying an rbac_scope column, so
chunk_columns_enumerated (AD-9) MUST report a violation. AST-parsed only; never imported."""


class Chunk:
    chunk_id: str = ""
    rbac_scope: str = ""  # the forbidden denormalised scope column (the stale-wall defect)
