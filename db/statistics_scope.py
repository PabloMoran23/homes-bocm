"""Publication scope for summary.json; validated again by the web build/runtime."""
from typing import Any


def create_statistics_scope(summary: dict[str, Any]) -> dict[str, Any]:
    scope = summary["buildScope"]
    if scope not in ("full", "madrid-public"):
        raise ValueError("statistics-scope: unknown buildScope")
    for key in ("byYear", "byTerritorio", "bySource"):
        if sum(row["count"] for row in summary[key]) != summary["total"]:
            raise ValueError(f"statistics-scope: {key} denominator mismatch")
    return {
        "version": 1,
        "buildScope": scope,
        "geography": "España" if scope == "full" else "Comunidad de Madrid",
        "coverage": "partial",
        "sources": [row["name"] for row in summary["bySource"]],
        "territories": [row["name"] for row in summary["byTerritorio"] if row["count"] > 0],
        "period": dict(summary["dateRange"]),
        "checkedAt": summary["generatedAt"],
        "denominator": {"population": "all-published-announcements", "count": summary["total"]},
        "limitations": "Cobertura parcial de las fuentes y territorios enumerados; no representa todos los anuncios ni permite comparar cobertura homogénea entre comunidades.",
    }
