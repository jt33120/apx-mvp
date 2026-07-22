"""Worker entrypoint boundary (AD-6).

Story 1.1 ships the boundary object only: a Procrastinate ``App`` with **zero**
tasks and an in-memory connector placeholder. The real PostgreSQL connector and
the tasks are wired by the store story and the ingestion stories. Resumable,
idempotent ingestion is a transaction property of the PostgreSQL-backed queue
(AD-5) — not built here.
"""

from procrastinate import App, testing

# In 1.1 there is no database yet (schema is story 1.3), so the boundary object
# uses the in-memory connector. The real PsycopgConnector is wired by the store
# story. No tasks are registered.
app = App(connector=testing.InMemoryConnector())
