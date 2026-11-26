"""Paso ``anuncios_update``: lee el tablón completo y escribe anuncios.jsonl.

Es un paso auxiliar: si el tablón falla, el resultado lleva ``status: failed``
(sin clave ``error``) para que el orquestador siga con proyectos y licencias y
no aparque el municipio. El fallo queda visible en el resumen del paso.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from municipio.anuncio_clase import clasificar
from municipio.gestiona_board import board_url_for, now_iso, read_board
from municipio.manifest import MunicipioManifest, load_yaml


def _write(manifest: MunicipioManifest, rows: list[dict[str, Any]], state: dict[str, Any]) -> None:
    out = manifest.ensure_output_dir()
    with (out / "anuncios.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out / "anuncios_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _clear(manifest: MunicipioManifest) -> None:
    for name in ("anuncios.jsonl", "anuncios_state.json"):
        path = manifest.output_dir / name
        if path.exists():
            path.unlink()


def update(manifest: MunicipioManifest, *, read=read_board) -> dict[str, Any]:
    # Nunca reutilizar una lectura anterior: si esta falla, no hay nada que sincronizar.
    _clear(manifest)
    board_url = board_url_for(load_yaml(manifest.path))
    if not board_url:
        return {"status": "skipped", "reason": "sin tablón Gestiona"}
    config = manifest.portal.config
    try:
        result = read(
            board_url,
            insecure_ssl=config.get("insecure_ssl") is True,
            delay_s=float(config.get("request_delay_s") or 0.4),
        )
    except Exception as exc:  # noqa: BLE001 - paso auxiliar, no aparca el municipio
        return {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"[:500], "board_url": board_url}
    captured = now_iso()
    rows = [
        {**rec, **clasificar(rec), "municipio_slug": manifest.slug, "capturado_at": captured}
        for rec in result.anuncios
    ]
    state = {
        "board_url": board_url,
        "capturado_at": captured,
        "clicks": result.clicks,
        "complete": not result.truncated,
        "rows": len(rows),
    }
    _write(manifest, rows, state)
    clases = Counter(row["clase"] for row in rows)
    return {
        "status": "ok",
        "rows": len(rows),
        "clicks": result.clicks,
        "truncated": result.truncated,
        "clases": dict(clases.most_common()),
    }
