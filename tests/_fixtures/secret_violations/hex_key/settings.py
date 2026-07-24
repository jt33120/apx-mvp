"""Deliberately violating fixture (story 1.8, AD-47): a HEX-encoded key literal. Its per-char
entropy (~3.9) sits below the base64 threshold — the app accepts hex keys, so this real evasion
must be caught by the pure-hex LENGTH leg, not entropy. Text-scanned only; never imported."""

KEY = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718"  # a FAKE 48-char hex key
