"""Operational CLI — bootstrap the first admin, and create users off-line.

    python -m apx.manage create-user --tenant cabinet --email patron@cabinet.fr \
        --name "Le Patron" --admin --scope pole-assurance --scope pole-penal

Reads DATABASE_URL from the environment. The password comes from APX_NEW_PASSWORD or an
interactive prompt — never a command-line argument, so it does not land in shell
history. The first admin is created this way; thereafter the cockpit manages the rest.
"""

from __future__ import annotations

import argparse
import getpass
import os
from collections.abc import Sequence

from apx.adapters.store_postgres.engine import make_session_factory
from apx.adapters.store_postgres.store import SqlStore


def _create_user(store: SqlStore, args: argparse.Namespace, password: str) -> str:
    return store.create_user(
        args.tenant, args.email, password, args.name, set(args.scope or []), is_admin=args.admin,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apx.manage")
    sub = parser.add_subparsers(dest="cmd", required=True)
    create = sub.add_parser("create-user", help="create a user (use --admin for the first admin)")
    create.add_argument("--tenant", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--admin", action="store_true")
    create.add_argument("--scope", action="append", default=[], help="repeatable")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.cmd == "create-user":
        password = os.environ.get("APX_NEW_PASSWORD") or getpass.getpass("Mot de passe : ")
        if not password:
            raise SystemExit("un mot de passe est requis (APX_NEW_PASSWORD ou saisie)")
        store = SqlStore(make_session_factory())
        uid = _create_user(store, args, password)
        scopes = sorted(args.scope or [])
        print(f"créé : {uid} · {args.email} · admin={args.admin} · scopes={scopes}")


if __name__ == "__main__":
    main()
