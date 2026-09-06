"""Railway/Railpack compatibility entrypoint.

Railway's Python autodetection may choose `uvicorn main:app`. Keep this tiny
shim so autodetection still runs the real Cashh Radar FastAPI application from
app.py.
"""

from app import app  # noqa: F401
