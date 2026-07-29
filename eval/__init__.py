"""APX evaluation substrate (Story 2.12, FR-54): the lifted gold corpus, the mechanical degradation
pipeline, the gold-set relevance mapping, and the harness that runs recall against the gold set in
CI (AD-34's merge gate).

This tree is OUTSIDE the product runtime (``apx/``) and OUTSIDE the test suite (``tests/``): the
corpus is a **configured data source** ingested through the real path, never a fixture (FR-33).
``eval`` imports ``apx`` (the ingestion path); ``apx`` never imports ``eval`` — the product does not
depend on the evaluation corpus.
"""
