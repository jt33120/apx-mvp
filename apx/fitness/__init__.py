"""Offline fitness (AD-2): can this run, unmodified, on one machine with no internet?

The frame — the offline env, the no-outbound-network boot, and the end-to-end
driver — exists from week one. The driver's end-to-end coverage grows as later
stories add ingest / index / rank / audit / export; it never fakes a stage.
"""
