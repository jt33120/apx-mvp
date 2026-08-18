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
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from apx.adapters.embedder_bgem3.bgem3 import Bgem3Embedder
from apx.adapters.originals_fs import FilesystemOriginalStore
from apx.adapters.store_postgres.crypto_types import cipher
from apx.adapters.store_postgres.opening import open_store
from apx.adapters.store_postgres.store import SqlStore, TenantAlreadyProvisioned
from apx.backup_bundle import read_bundle, restore_originals, write_bundle
from apx.core.app.ingest import SCHEMA_VERSION
from apx.core.app.line import place_line
from apx.core.app.rank import identity_inputs, produce_ranking
from apx.core.domain.chunking import chunking_config
from apx.core.domain.config import cascade_config
from apx.core.ports.embedding import Embedder
from apx.core.ports.judge import Judge
from apx.wiring import open_judge


def _open_store() -> SqlStore:
    """The store wired to the head journal (AD-35) — so a manage command's audited writes and a
    restore both reconcile the chain head outside the restorable store.

    **Required, since Story 5.9.** It was optional, and the consequence was precise: with
    ``APX_HEAD_JOURNAL`` unset, ``reconcile_heads`` returned an empty list and ``manage restore``
    printed its ordinary success line — the one blessed destructive operation, performing no
    continuity check at all and saying nothing about having skipped it. Absence is refusal here,
    on the same gate as the encryption key."""
    return open_store()


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


def _originals() -> FilesystemOriginalStore:
    """The retained-original store this deployment actually uses — **required** for a backup.

    ``from_env`` falls back to the host temp directory when ``APX_DATA_PATH`` is unset, which is a
    reasonable last resort for a dev run and a disaster for a backup: the fallback directory is
    empty, so the bundle would be written with zero originals in it and would report success. The
    one operation whose entire job is completeness refuses a configuration it cannot be complete
    under (the same gate ``_open_store`` puts on the head journal).
    """
    if not (os.environ.get("APX_DATA_PATH") or "").strip():
        raise RuntimeError(
            "APX_DATA_PATH is not set — the retained originals cannot be located, and a backup "
            "taken without them would report success over a tenant whose documents are absent "
            "(AD-32)")
    return FilesystemOriginalStore.from_env()


def backup(store: SqlStore, tenant: str, out_path: str) -> str:
    """On-demand backup of a tenant to a sealed bundle (AD-32) — every table the model has, plus
    the retained originals as the ciphertext they already are. The outcome is recorded WITH its
    coverage, so 'no backup within the interval' and 'the backup was incomplete' are both
    answerable."""
    b = store.backup_tenant(tenant)
    coverage = write_bundle(Path(out_path), b, _originals(), cipher())
    # An incomplete backup is recorded as a FAILURE even though the bundle was written. AD-32's
    # criterion is a COMPLETE restorable backup, and the failure it exists to prevent is "a backup
    # whose failure nobody knew about" — so a retained pièce with no document on the volume makes
    # the worklist say the tenant has no good backup, rather than a green line over a known hole.
    # The bundle is still written: it is better than nothing, and refusing to write it would leave
    # the firm with neither.
    outcome = "success" if coverage.is_complete else "failure"
    store.record_backup(
        tenant, outcome, byte_size=coverage.byte_size, detail=coverage.sentence_fr())
    return f"backup : tenant={tenant} → {out_path} ({coverage.sentence_fr()})"


def restore(store: SqlStore, in_path: str) -> str:
    """Restore a tenant from a sealed bundle into an EMPTY store (AD-32); reconciles the head — a
    restore that moved the head backwards is a truncation, named here (AD-35).

    The rows go back first: that transaction re-verifies the AD-43 chain and rolls the whole restore
    back if it does not hold, so a rejected backup never leaves blobs behind on the data volume."""
    bundle = read_bundle(Path(in_path), cipher())
    b = bundle.backup
    recs = store.restore_tenant(b)
    covered = restore_originals(Path(in_path), bundle, _originals())
    truncated = [r.scope for r in recs if r.truncated]
    # Story 5.9 — a FORK is reported too, and apart. Reporting only truncations meant a restore of
    # a record that had been rewritten and re-chained to the same length printed the ordinary
    # success line: the operator was told the restore worked, on the one finding that says the
    # record in front of them is not the record.
    forked = [r.scope for r in recs if r.forked]
    msg = (f"restore : tenant={b.tenant} restauré depuis {in_path} "
           f"({covered.originals} originaux)")
    if covered.orphaned_pieces:
        msg += (f" — ATTENTION : {covered.orphaned_pieces} pièce(s) conservée(s) sans document "
                "d'origine (la sauvegarde elle-même était incomplète ; le registre les atteste "
                "et la visionneuse ne peut pas les ouvrir)")
    if truncated:
        msg += (f" — ATTENTION : troncature détectée pour {truncated} (la tête vive est en deçà "
                "du journal ; acquitter via l'override DR)")
    if forked:
        msg += (f" — ATTENTION : registre réécrit pour {forked} (la valeur de chaîne diffère de "
                "celle du témoin extérieur ; acquitter via l'override DR)")
    return msg


def rank(
    store: SqlStore, *, tenant: str, matter: str, actor: str, scopes: set[str],
    embedder: Embedder | None = None, judge: Judge | None = None,
) -> str:
    """Produce ONE ranked order for a *matter* and mint its *ranking version* (FR-39, AD-23).

    **The first production caller of the ranking act.** Retro action C4 found that
    ``produce_ranking`` had none at all: no route, no worker job, no command — twenty-two shipped
    stories standing on an act nobody could perform. It is an operator command rather than the
    lawyer's gesture on purpose. AD-6 says any operation whose cost scales with the size of a
    *matter* is a **queued job** and that the HTTP layer validates, authorises, enqueues and
    returns; the cascade is one model call per uncertain *pièce*, so it does not belong in a
    request. A CLI command is where a long job legitimately runs synchronously — the same place
    ``backup`` runs — and it makes the act performable today without pretending the queue exists.

    Every identity input is sourced from the thing that actually produced the order: the model half
    from the judge this deployment composed (never from configuration, which records a preference
    and would name a model that never ran), the cascade numbers from the tenant's own
    configuration-as-data, and the chunking/embedder/schema halves from the build that read the
    corpus.
    """
    if not store.matter_is_held(tenant=tenant, matter=matter, scopes=scopes):
        # Fail closed BEFORE anything is read. ``read_case_theory`` answers None for out-of-scope
        # and for absent alike (FR-14, non-disclosing) — and a None case theory is also how the
        # act says "rank on intrinsic signals". Without this gate, a caller who does not hold the
        # matter would get a complete, permanently fingerprinted intrinsic ranking whose header
        # reads « signaux intrinsèques nommés » — the name of a deliberate methodology — for a
        # theory that was simply never fetched.
        raise ValueError(
            f"matter {matter!r}: not held under the scope(s) given — nothing was read (FR-14)")
    units = store.cascade_units(matter, tenant, scopes)
    theory = store.read_case_theory(tenant=tenant, matter=matter, scopes=scopes)
    current = theory.current if theory is not None else None
    embedder = embedder or Bgem3Embedder()
    judge = judge or open_judge(store, tenant)
    get = lambda key: store.get_config(tenant, key)  # noqa: E731 — the config-as-data getter
    version = produce_ranking(
        units,
        case_theory=current.text if current is not None else None,
        scorer=store.semantic_scorer(embedder),
        judge=judge,
        config=cascade_config(get),
        inputs=identity_inputs(
            judge=judge.identity,
            case_theory_version_id=current.version_id if current is not None else None,
            embedder_model_id=embedder.model_id, embedder_model_version=embedder.model_version,
            chunking_config_version=chunking_config(get).version,
            schema_version=SCHEMA_VERSION),
        tenant=tenant, matter=matter, actor=actor, scopes=scopes, recorder=store)
    basis = "théorie du cas" if current is not None else "signaux intrinsèques"
    return (f"rank : dossier={matter} → classement n° {version.version_no} "
            f"({len(units)} pièces, base : {basis}, juge : {judge.identity.model})")


def place(store: SqlStore, *, tenant: str, matter: str, actor: str, scopes: set[str]) -> str:
    """Draw and commit **the line** over the *matter*'s latest *ranking version* (FR-17).

    Shipped beside ``rank`` because a ranking with no line is a *matter* the product cannot finish
    reasoning about: the retained and discarded sets are views over the ranked order **and the
    cut**, so with no cut every row reads *classées, en attente de la ligne*, the *sampling run*
    refuses to start, and no *confidence bound* can exist. A re-rank supersedes the previous
    placement, so this is also the remedy for the state a second ``rank`` leaves behind."""
    if not store.matter_is_held(tenant=tenant, matter=matter, scopes=scopes):
        raise ValueError(
            f"matter {matter!r}: not held under the scope(s) given — nothing was read (FR-14)")
    placement = place_line(store, tenant=tenant, matter=matter, actor=actor, scopes=scopes)
    if placement is None:
        # A real answer, not a failure: the tool commits to no line when no pièce is in a retain
        # band (recall-first — a line is never fabricated).
        return (f"place-line : dossier={matter} — aucune ligne posée (aucune pièce en bande "
                "retenue ; la ligne n'est jamais fabriquée)")
    return (f"place-line : dossier={matter} → dernière pièce retenue "
            f"{placement.last_retained_piece_id} (classement n° {placement.version_no})")


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
    bk = sub.add_parser("backup", help="on-demand logical backup of a tenant to a file (AD-32)")
    bk.add_argument("--tenant", required=True)
    bk.add_argument("--out", required=True, help="destination file (encrypted content at rest)")
    rs = sub.add_parser("restore", help="restore a tenant from a backup file into an empty store")
    rs.add_argument("--from", dest="src", required=True, help="the backup file")
    rk = sub.add_parser(
        "rank", help="produce a ranked order for a matter and mint its ranking version (FR-39)")
    rk.add_argument("--tenant", required=True)
    rk.add_argument("--matter", required=True)
    rk.add_argument("--actor", required=True, help="who is recorded as having run the act (FR-24)")
    # Required and repeatable, never "all scopes": the act is performed AS somebody, and an
    # operator command that could rank across every wall would be the one caller for which the
    # Chinese wall does not exist.
    rk.add_argument("--scope", action="append", default=[], required=True, help="repeatable")
    pl = sub.add_parser(
        "place-line", help="draw and commit the line over the matter's latest ranking (FR-17)")
    pl.add_argument("--tenant", required=True)
    pl.add_argument("--matter", required=True)
    pl.add_argument("--actor", required=True)
    pl.add_argument("--scope", action="append", default=[], required=True, help="repeatable")
    sub.add_parser(
        "worker", help="run the resumable import worker (applies the queue schema first)")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    from apx.api.logging import install_secret_redaction

    install_secret_redaction()  # scrub secrets from any log this CLI emits (AD-47), like the app
    args = build_parser().parse_args(argv)
    if args.cmd == "worker":
        # The resumable import worker (Story 2.2, AD-6). Applies Procrastinate's queue schema
        # (idempotent, kept OUT of the Alembic chain — Procrastinate owns it, AD-17) then consumes
        # the queue, committing one pièce per unit against the application-owned ledger.
        from apx.worker.app import app as worker_app
        with worker_app.open():
            worker_app.schema_manager.apply_schema()
            worker_app.run_worker(install_signal_handlers=True)
        return
    if args.cmd == "provision":
        password = os.environ.get("APX_NEW_PASSWORD") or getpass.getpass("Mot de passe admin : ")
        if not password:
            raise SystemExit("un mot de passe est requis (APX_NEW_PASSWORD ou saisie)")
        store = _open_store()
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
        store = _open_store()
        uid = _create_user(store, args, password)
        scopes = sorted(args.scope or [])
        print(f"créé : {uid} · {args.email} · admin={args.admin} · scopes={scopes}")
    elif args.cmd == "ensure-admin":
        print(ensure_admin(_open_store()))
    elif args.cmd == "rekey":
        print(rekey(_open_store()))
    elif args.cmd == "backup":
        print(backup(_open_store(), args.tenant, args.out))
    elif args.cmd == "restore":
        print(restore(_open_store(), args.src))
    elif args.cmd == "rank":
        print(rank(_open_store(), tenant=args.tenant, matter=args.matter, actor=args.actor,
                   scopes=set(args.scope)))
    elif args.cmd == "place-line":
        print(place(_open_store(), tenant=args.tenant, matter=args.matter, actor=args.actor,
                    scopes=set(args.scope)))


if __name__ == "__main__":
    main()
