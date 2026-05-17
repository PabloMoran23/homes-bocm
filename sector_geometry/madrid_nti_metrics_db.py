"""Persistencia SQLite para métricas NTI (checkpoint por PDF / LLM)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = POC_ROOT / "db" / "poc_local.sqlite"
SCHEMA_METRICS = POC_ROOT / "db" / "schema_sigma_metrics.sql"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(con: sqlite3.Connection) -> None:
    if SCHEMA_METRICS.is_file():
        con.executescript(SCHEMA_METRICS.read_text(encoding="utf-8"))
    con.commit()


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path or DEFAULT_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=60)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    ensure_schema(con)
    return con


def load_done_pdf_paths(con: sqlite3.Connection) -> set[str]:
    cur = con.execute("SELECT pdf_path FROM sigma_pdf_metric")
    return {str(r[0]) for r in cur.fetchall()}


def upsert_pdf_metric(con: sqlite3.Connection, row: dict[str, Any], *, llm_model: str = "") -> None:
    now = _utc_now()
    con.execute(
        """
        INSERT INTO sigma_pdf_metric (
          expediente_grupo, pdf_path, pdf_name, doc_type, doc_role, method, llm_model,
          processed_at, num_viviendas_max, sup_total_m2, sup_edificable_m2,
          tipo_vivienda, uso_principal, texto_util, row_json, llm_error, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pdf_path) DO UPDATE SET
          expediente_grupo = excluded.expediente_grupo,
          pdf_name = excluded.pdf_name,
          doc_type = excluded.doc_type,
          doc_role = excluded.doc_role,
          method = excluded.method,
          llm_model = excluded.llm_model,
          processed_at = excluded.processed_at,
          num_viviendas_max = excluded.num_viviendas_max,
          sup_total_m2 = excluded.sup_total_m2,
          sup_edificable_m2 = excluded.sup_edificable_m2,
          tipo_vivienda = excluded.tipo_vivienda,
          uso_principal = excluded.uso_principal,
          texto_util = excluded.texto_util,
          row_json = excluded.row_json,
          llm_error = excluded.llm_error,
          updated_at = excluded.updated_at
        """,
        (
            row.get("expediente_grupo"),
            row.get("pdf_path"),
            row.get("pdf_name"),
            row.get("doc_type"),
            row.get("doc_role"),
            row.get("method"),
            llm_model or None,
            row.get("processed_at") or now,
            row.get("num_viviendas_max"),
            row.get("sup_total_m2"),
            row.get("sup_edificable_m2"),
            row.get("tipo_vivienda"),
            row.get("uso_principal"),
            1 if row.get("texto_util") else 0,
            json.dumps(row, ensure_ascii=False),
            row.get("llm_error"),
            now,
        ),
    )


def fetch_pdf_rows_for_expediente(con: sqlite3.Connection, grupo: str) -> list[dict[str, Any]]:
    cur = con.execute(
        "SELECT row_json FROM sigma_pdf_metric WHERE expediente_grupo = ? ORDER BY id",
        (grupo,),
    )
    out: list[dict[str, Any]] = []
    for r in cur.fetchall():
        try:
            out.append(json.loads(r["row_json"]))
        except json.JSONDecodeError:
            continue
    return out


def upsert_expediente_metric(
    con: sqlite3.Connection,
    grupo: str,
    *,
    denominacion: str = "",
    fase_sigma: str = "",
    agg: dict[str, Any],
) -> None:
    metrics = agg.get("metrics") or {}
    now = _utc_now()
    con.execute(
        """
        INSERT INTO sigma_expediente_metric (
          expediente_grupo, denominacion, fase_sigma, familia_expediente, genera_vivienda_nueva,
          num_viviendas_max, sup_total_m2, sup_edificable_m2,
          metrics_json, hechos_json, fuentes_pdf_json, doc_role_principal, pdfs_procesados, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(expediente_grupo) DO UPDATE SET
          denominacion = excluded.denominacion,
          fase_sigma = excluded.fase_sigma,
          familia_expediente = excluded.familia_expediente,
          genera_vivienda_nueva = excluded.genera_vivienda_nueva,
          num_viviendas_max = excluded.num_viviendas_max,
          sup_total_m2 = excluded.sup_total_m2,
          sup_edificable_m2 = excluded.sup_edificable_m2,
          metrics_json = excluded.metrics_json,
          hechos_json = excluded.hechos_json,
          fuentes_pdf_json = excluded.fuentes_pdf_json,
          doc_role_principal = excluded.doc_role_principal,
          pdfs_procesados = excluded.pdfs_procesados,
          updated_at = excluded.updated_at
        """,
        (
            grupo,
            denominacion or None,
            fase_sigma or None,
            metrics.get("familia_expediente"),
            metrics.get("genera_vivienda_nueva"),
            metrics.get("num_viviendas_max"),
            metrics.get("sup_total_m2"),
            metrics.get("sup_edificable_m2"),
            json.dumps(metrics, ensure_ascii=False),
            json.dumps(agg.get("hechos") or [], ensure_ascii=False),
            json.dumps(agg.get("fuentes_pdf") or [], ensure_ascii=False),
            agg.get("doc_role_principal"),
            int(agg.get("pdfs_procesados") or 0),
            now,
        ),
    )


def set_state(con: sqlite3.Connection, key: str, value: str) -> None:
    con.execute(
        """
        INSERT INTO sigma_pdf_extract_state (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, _utc_now()),
    )


def get_state(con: sqlite3.Connection, key: str) -> str | None:
    row = con.execute("SELECT value FROM sigma_pdf_extract_state WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row else None


def count_metrics(con: sqlite3.Connection) -> dict[str, int]:
    pdf_total = con.execute("SELECT COUNT(*) FROM sigma_pdf_metric").fetchone()[0]
    exp_total = con.execute("SELECT COUNT(*) FROM sigma_expediente_metric").fetchone()[0]
    with_viv = con.execute(
        "SELECT COUNT(*) FROM sigma_expediente_metric WHERE num_viviendas_max IS NOT NULL"
    ).fetchone()[0]
    return {
        "pdf_metrics": int(pdf_total),
        "expediente_metrics": int(exp_total),
        "expedientes_con_viviendas": int(with_viv),
    }
