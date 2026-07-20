from __future__ import annotations


class DomainError(Exception):
    """Base class for typed errors raised by services/repositories.

    Kept independent of FastAPI (no HTTP concepts here) so the same
    exceptions are meaningful to the CLI as well as the API — src/api/errors.py
    is the only place that knows how to translate these into HTTP responses.
    """


class TickerNotFoundError(DomainError):
    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"No data available for ticker {ticker!r}")


class InsufficientDataError(DomainError):
    def __init__(self, ticker: str, reason: str):
        self.ticker = ticker
        self.reason = reason
        super().__init__(f"Insufficient data for {ticker!r}: {reason}")
