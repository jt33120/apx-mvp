"""Deliberately violating fixture (story 1.8, AD-47): a hardcoded GitHub personal access token.
no_secret_in_source MUST fire on the named-credential pattern. Text-scanned only; never imported
(and under tests/, outside the real scan). The token below is FAKE."""

TOKEN = "github_pat_11ABCDEFG0000000000_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789AbCdEfGh"
