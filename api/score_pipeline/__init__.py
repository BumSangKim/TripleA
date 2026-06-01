"""Independent score-based pipeline architecture.

This package intentionally does not import existing strategy judgment engines.
It may reuse infrastructure such as config loading, data access, and tests, but
the investment decision flow is defined by the contracts in this package.
"""

from api.score_pipeline.score_store import store_score

__all__ = ["store_score"]
