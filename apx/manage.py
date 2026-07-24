"""Operational CLI — provision a tenant, bootstrap the first admin, create users off-line.

    python -m apx.manage provision --tenant cabinet --admin-email patron@cabinet.fr \
        --admin-name "Le Patron" --scope pole-assurance --taxonomy conclusions --taxonomy pièce

    python -m apx.manage create-user --tenant cabinet --email patron@cabinet.fr \
        --name "Le Patron" --admin --scope pole-assurance --scope pole-penal

Reads DATABASE_URL from the environment. The password comes from APX_NEW_PASSWORD or an
interactive prompt — never a command-line argument, so it does not land in shell history.
`provision` is the first-run bootstrap surface (AD-25): it establishes a tenant's first
administrative grant and its taxonomy in one audited act; thereafter the authed cockpit
manages configuration, users and scopes.
"""

from __future__ import annotations

import argparse
import getpass
import os
from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError

from apx.adapters.store_postgres.engine import make_session_factory
from apx.adapters.store_postgres.store import SqlStore, TenantAlreadyProvisioned


def _create_user(store: SqlStore, args: argparse.Namespace, password: str) -> str:
    return store.create_user(
        args.tenant, args.email, password, args.name, set(args.scope or []), is_admin=args.admin,
    )


def ensure_admin(store: SqlStore) -> str:
    """Idempotent first-admin bootstrap from the environment — for a fresh deployment,
    run once on boot (the entrypoint calls this). Creates the admin only if it does not
    already exist; a no-op thereafter. Reads APX_BOOTSTRAP_ADMIN_EMAIL / _PASSWORD (both
    required to do anything) / _NAME / _TENANT / _SCOPES (comma-separated)."""
    email = os.environ.get("APX_BOOTSTRAP_ADMIN_EMAIL")
    password = os.environ.get("APX_BOOTSTRAP_ADMIN_PASSWORD")
    if not email or not password:
        return "bootstrap: APX_BOOTSTRAP_ADMIN_EMAIL/_PASSWORD not set — nothing to do"
    tenant = os.environ.get("APX_BOOTSTRAP_ADMIN_TENANT", "cabinet")
    name = os.environ.get("APX_BOOTSTRAP_ADMIN_NAME", email)
    raw_scopes = os.environ.get("APX_BOOTSTRAP_ADMIN_SCOPES", "").split(",")
    scopes = {s.strip() for s in raw_scopes if s.strip()}
    try:
        store.create_user(tenant, email, password, name, scopes, is_admin=True)
        return f"bootstrap: admin {email} created (tenant={tenant}, scopes={sorted(scopes)})"
    except IntegrityError:
        return f"bootstrap: admin {email} already exists — no change"


def rekey(store: SqlStore) -> str:
    """Rotate the encryption key in place (story 1.8, AD-47): re-encrypt every application-
    encrypted value under the current PRIMARY key and record the rotation on each data-bearing
    tenant's audit chain — atomically. Runbook (README): (1) RESTART the app with the new key as
    APX_ENCRYPTION_KEY and the old as APX_ENCRYPTION_KEYS_OLD, (2) run this, (3) restart dropping
    the old key. The restart is required because the live cipher is process-cached; it is a config
    change, not a redeploy, and needs no re-index (the searchable surfaces are never encrypted)."""
    from apx.core.domain.crypto import key_fingerprint, load_key_from_env

    fingerprint = key_fingerprint(load_key_from_env())
    count = store.rekey_and_record(fingerprint)
    firms = store.tenants()
    return (f"rekey: {count} value(s) re-encrypted under key {fingerprint}; "
            f"rotation recorded for {len(firms)} tenant(s)")


def _provision(store: SqlStore, args: argparse.Namespace, password: str) -> str:
    return store.provision_tenant(
        args.tenant, args.admin_email, password, args.admin_name,
        set(args.scope or []), list(args.taxonomy or []),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apx.manage")
    sub = parser.add_subparsers(dest="cmd", required=True)
    prov = sub.add_parser(
        "provision", help="provision a tenant: first admin + scopes + taxonomy (audited, AD-25)")
    prov.add_argument("--tenant", required=True)
    prov.add_argument("--admin-email", required=True)
    prov.add_argument("--admin-name", required=True)
    prov.add_argument("--scope", action="append", default=[], help="repeatable")
    prov.add_argument("--taxonomy", action="append", default=[], help="repeatable label")
    create = sub.add_parser("create-user", help="create a user (use --admin for the first admin)")
    create.add_argument("--tenant", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--admin", action="store_true")
    create.add_argument("--scope", action="append", default=[], help="repeatable")
    sub.add_parser("ensure-admin", help="idempotent first-admin bootstrap from the environment")
    sub.add_parser("rekey", help="rotate the encryption key in place (re-encrypt + audit)")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    from apx.api.logging import install_secret_redaction

    install_secret_redaction()  # scrub secrets from any log this CLI emits (AD-47), like the app
    args = build_parser().parse_args(argv)
    if args.cmd == "provision":
        password = os.environ.get("APX_NEW_PASSWORD") or getpass.getpass("Mot de passe admin : ")
        if not password:
            raise SystemExit("un mot de passe est requis (APX_NEW_PASSWORD ou saisie)")
        store = SqlStore(make_session_factory())
        try:
            uid = _provision(store, args, password)
        except TenantAlreadyProvisioned as exc:
            raise SystemExit(f"déjà provisionné : {exc}") from exc
        scopes, taxonomy = sorted(args.scope or []), list(args.taxonomy or [])
        print(f"provisionné : tenant={args.tenant} · admin={uid} ({args.admin_email}) · "
              f"scopes={scopes} · taxonomie={len(taxonomy)} label(s)")
    elif args.cmd == "create-user":
        password = os.environ.get("APX_NEW_PASSWORD") or getpass.getpass("Mot de passe : ")
        if not password:
            raise SystemExit("un mot de passe est requis (APX_NEW_PASSWORD ou saisie)")
        store = SqlStore(make_session_factory())
        uid = _create_user(store, args, password)
        scopes = sorted(args.scope or [])
        print(f"créé : {uid} · {args.email} · admin={args.admin} · scopes={scopes}")
    elif args.cmd == "ensure-admin":
        print(ensure_admin(SqlStore(make_session_factory())))
    elif args.cmd == "rekey":
        print(rekey(SqlStore(make_session_factory())))


if __name__ == "__main__":
    main()
