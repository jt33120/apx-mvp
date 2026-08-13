"""A sequence generator on the evidential table."""
from sqlalchemy import Sequence

audit_seq = Sequence("audit_record_seq")
