"""Raw SQL reaching for the generator instead of the head row."""
from sqlalchemy import text

STMT = text("SELECT nextval('audit_record_seq')")
