"""TrailCut ingestion.

Turns a CAS PDF (bytes, in memory) into a PII-free
:class:`trailcut_engine.portfolio.Portfolio`. Nothing here writes to disk,
logs, or keeps the PDF, password, PAN, email, phone or folio numbers.
"""

__version__ = "0.0.0"
