"""Deliberately violating fixture (story 1.8, AD-47): a hardcoded high-entropy key literal with
no recognizable prefix — the dangerous case a pattern list misses. no_secret_in_source MUST fire
on the entropy leg. Text-scanned only; never imported (and under tests/, outside the real scan)."""

API_KEY = "SavGoemmyVvu9lseGv04DjBzdXYmcvZG3xQ7"  # a FAKE 36-char key — forbidden in source
