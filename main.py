"""Railway/Railpack compatibility entrypoint.

Railway's Python autodetection may choose `uvicorn main:app`. Keep this tiny
shim pointed at the real FastAPI app while registering the canonical Cashh Radar
opportunity-to-outcome loop.
"""

from app import app  # noqa: F401
from cashh_loop import register_cashh_loop

register_cashh_loop(app)
