"""REST API for MarketRadar (Task 10).

This package is a thin presentation layer over src/pipeline/pipeline.py.
It must never import src.ai, src.fetchers, or src.reporting.report_generator
/ formatter directly - see src/api/routes.py's module docstring for the
full reasoning. The only pipeline-produced business objects it touches
are the plain data shapes in src.reporting.models / src.insights.models
(dataclasses with no logic in them), used solely to type-check the
JSON conversion in src/api/models.py.
"""

from __future__ import annotations
