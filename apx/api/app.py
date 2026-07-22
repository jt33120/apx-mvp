"""HTTP surface boundary (AD-6).

Story 1.1 ships the boundary object only: a FastAPI application with **zero**
routes. Routes are added by the stories that own them (auth 1.5, ingestion 2.x,
retrieval 3.x). Keeping this empty is the point — 1.1 is scaffolding.
"""

from fastapi import FastAPI

app = FastAPI(title="APX", version="0.0.0")
