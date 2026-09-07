"""Railway/Railpack compatibility entrypoint.

Railway's Python autodetection may choose `uvicorn main:app`. Keep this tiny
shim so autodetection runs the canonical Cashh Radar launcher, including the
unified opportunity-to-outcome loop.
"""

from launcher import app  # noqa: F401
