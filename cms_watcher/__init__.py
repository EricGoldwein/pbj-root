"""Read-only CMS release + PBJ320 downstream-freshness watcher.

Observe only — never download datasets, rebuild artifacts, mutate policy,
or trigger deploys.
"""

from .compare import evaluate_source
from .registry import SOURCE_REGISTRY, dependency_graph_rows

__all__ = [
    "SOURCE_REGISTRY",
    "dependency_graph_rows",
    "evaluate_source",
]

__version__ = "1.0.0"
