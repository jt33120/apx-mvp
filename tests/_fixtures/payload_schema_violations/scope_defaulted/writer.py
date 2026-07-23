"""Deliberately violating fixture: write_chunk gives rbac_scope a default, so
scope_arg_required (AD-9/AD-13) MUST report a violation. AST-parsed only; never imported."""


def write_chunk(payload: object, *, rbac_scope: str = "wall") -> str:
    return rbac_scope
