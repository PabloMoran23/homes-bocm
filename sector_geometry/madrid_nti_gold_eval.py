#!/usr/bin/env python3
"""
Evalúa el pipeline NTI (selección por rol + merge) contra dataset gold.

Uso:
  python3 -m sector_geometry.madrid_nti_gold_eval
  python3 -m sector_geometry.madrid_nti_gold_eval --llm --report output/madrid_nti_gold_eval_pipeline.md
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from sector_geometry.madrid_nti_doc_roles import classify_doc_role
from sector_geometry.madrid_nti_pdf_extract import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    POC_ROOT,
    _load_index_by_grupo,
    process_pdf_job,
)
from sector_geometry.madrid_nti_pdf_metrics import METRIC_KEYS, merge_expediente_metrics
from sector_geometry.madrid_nti_pdf_select import build_job_from_path, select_pipeline_jobs

GOLD_PATH = POC_ROOT / "output" / "madrid_nti_gold_labels.json"
EVAL_METRICS = (
    "num_viviendas_max",
    "sup_total_m2",
    "sup_edificable_m2",
    "genera_vivienda_nueva",
)


def _num_close(gold: float | int | None, pred: float | int | None, *, rel_tol: float = 0.02) -> bool:
    if gold is None and pred is None:
        return True
    if gold is None or pred is None:
        return False
    g, p = float(gold), float(pred)
    if g == 0:
        return abs(p) < 1e-6
    return abs(g - p) <= max(1.0, abs(g) * rel_tol)


def _str_match(gold: str | None, pred: str | None) -> bool:
    if not gold and not pred:
        return True
    if not gold or not pred:
        return False
    g, p = gold.lower().strip(), pred.lower().strip()
    if g == p:
        return True
    if g in p or p in g:
        return True
    # familias relacionadas
    pairs = {
        ("probable_si", "probable_sin_cifra"),
        ("stock_existente_o_rehabilitacion", "no"),
    }
    return (g, p) in pairs or (p, g) in pairs


def compare_fields(gold: dict[str, Any], pred: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for k in keys:
        g, p = gold.get(k), pred.get(k)
        if k == "num_viviendas_max":
            ok = _num_close(g, p, rel_tol=0) and (g is None or p is None or int(g) == int(p))
        elif k in ("sup_total_m2", "sup_edificable_m2"):
            ok = _num_close(g, p)
        else:
            ok = _str_match(g if isinstance(g, str) else None, p if isinstance(p, str) else None)
        fields[k] = {"gold": g, "pred": p, "match": ok}
    return fields


def run_eval(*, use_llm: bool, max_pages: int, max_pdfs_per_exp: int) -> dict[str, Any]:
    data = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    index_by_g = _load_index_by_grupo()
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL) if use_llm else None

    # --- eval por PDF (muestras gold) ---
    pdf_comparisons: list[dict[str, Any]] = []
    for sample in data.get("samples") or []:
        pdf_path = POC_ROOT / sample["pdf_path"]
        if not pdf_path.is_file():
            continue
        job = build_job_from_path(
            sample["expediente_grupo"],
            pdf_path,
            meta={"titulo": pdf_path.name, "rutaCarpetas": ""},
        )
        pred = process_pdf_job(
            job,
            client=client,
            use_llm=use_llm,
            llm_if_regex_empty=not use_llm,
            max_pages=max_pages,
        )
        keys = tuple(k for k in METRIC_KEYS if k in sample or sample.get(k) is None)
        fields = compare_fields(sample, pred, keys)
        pdf_comparisons.append(
            {
                "expediente_grupo": sample["expediente_grupo"],
                "pdf_name": pdf_path.name,
                "doc_role": sample.get("doc_role") or pred.get("doc_role"),
                "fields": fields,
                "field_accuracy": sum(1 for f in fields.values() if f["match"]) / max(len(fields), 1),
                "gold_notes": sample.get("gold_notes"),
            }
        )

    # --- eval por expediente (pipeline + merge) ---
    exp_gold = {e["expediente_grupo"]: e for e in data.get("expediente_expectations") or []}
    all_jobs: list[dict[str, Any]] = []
    for sample in data.get("samples") or []:
        pdf_path = POC_ROOT / sample["pdf_path"]
        if pdf_path.is_file():
            all_jobs.append(
                build_job_from_path(
                    sample["expediente_grupo"],
                    pdf_path,
                    meta={"titulo": pdf_path.name, "rutaCarpetas": ""},
                )
            )

    pipeline_jobs = select_pipeline_jobs(all_jobs, max_pdfs_per_exp=max_pdfs_per_exp)
    by_exp_rows: dict[str, list[dict[str, Any]]] = {}
    for job in pipeline_jobs:
        row = process_pdf_job(
            job,
            client=client,
            use_llm=use_llm,
            llm_if_regex_empty=not use_llm,
            max_pages=max_pages,
        )
        by_exp_rows.setdefault(job["grupo"], []).append(row)

    exp_comparisons: list[dict[str, Any]] = []
    for grupo, gold in exp_gold.items():
        rows = by_exp_rows.get(grupo) or []
        idx = index_by_g.get(grupo) or {}
        agg = merge_expediente_metrics(
            rows,
            prefer_llm=use_llm,
            denominacion=str(idx.get("EXP_TX_DENOM") or ""),
            familia_hint=str(gold.get("familia") or ""),
        )
        pred_metrics = agg.get("metrics") or {}
        fields = compare_fields(gold, pred_metrics, EVAL_METRICS)
        exp_comparisons.append(
            {
                "expediente_grupo": grupo,
                "familia_gold": gold.get("familia"),
                "familia_pred": pred_metrics.get("familia_expediente"),
                "pdfs_pipeline": [r.get("pdf_name") for r in rows],
                "hechos": agg.get("hechos"),
                "fields": fields,
                "field_accuracy": sum(1 for f in fields.values() if f["match"]) / len(EVAL_METRICS),
                "gold_notes": gold.get("gold_notes"),
            }
        )

    def mean_acc(items: list[dict[str, Any]]) -> float:
        return sum(i["field_accuracy"] for i in items) / len(items) if items else 0.0

    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "pipeline_llm" if use_llm else "pipeline_regex",
        "n_pdf_samples": len(pdf_comparisons),
        "n_expedientes": len(exp_comparisons),
        "mean_pdf_field_accuracy": mean_acc(pdf_comparisons),
        "mean_expediente_field_accuracy": mean_acc(exp_comparisons),
        "pdf_comparisons": pdf_comparisons,
        "expediente_comparisons": exp_comparisons,
    }


def format_report(summary: dict[str, Any]) -> str:
    lines = [
        f"# Evaluación gold — {summary['mode']}",
        "",
        f"- PDFs evaluados: {summary['n_pdf_samples']} — precisión media: **{summary['mean_pdf_field_accuracy']:.1%}**",
        f"- Expedientes (pipeline+merge): {summary['n_expedientes']} — precisión media: **{summary['mean_expediente_field_accuracy']:.1%}**",
        "",
        "## Por expediente (pipeline)",
        "",
    ]
    for c in summary["expediente_comparisons"]:
        lines.append(f"### {c['expediente_grupo']}")
        lines.append(f"- Familia: gold `{c['familia_gold']}` → pred `{c['familia_pred']}`")
        lines.append(f"- PDFs pipeline: {', '.join(c['pdfs_pipeline'])}")
        lines.append(f"- Campos OK: {c['field_accuracy']:.0%}")
        if c.get("gold_notes"):
            lines.append(f"- Notas: {c['gold_notes']}")
        lines.append("")
        lines.append("| Campo | Gold | Pred | OK |")
        lines.append("|-------|------|------|-----|")
        for k, f in c["fields"].items():
            g = f["gold"] if f["gold"] is not None else "—"
            p = f["pred"] if f["pred"] is not None else "—"
            lines.append(f"| {k} | {g} | {p} | {'✓' if f['match'] else '✗'} |")
        if c.get("hechos"):
            lines.append("")
            lines.append("Hechos extraídos:")
            for h in c["hechos"]:
                lines.append(
                    f"- `{h['metrica']}` = {h['valor']} ({h['confianza']}, {h['doc_role']}, {h['pdf_name']})"
                )
        lines.append("")

    lines.extend(["## Por PDF (gold directo)", ""])
    for c in summary["pdf_comparisons"]:
        lines.append(f"### {c['expediente_grupo']} — `{c['pdf_name']}` ({c['doc_role']})")
        lines.append(f"Precisión: {c['field_accuracy']:.0%}")
        for k, f in c["fields"].items():
            mark = "✓" if f["match"] else "✗"
            lines.append(f"- {k}: gold={f['gold']} pred={f['pred']} {mark}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Evalúa pipeline vs gold.")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--max-pdfs-per-exp", type=int, default=8)
    ap.add_argument("--report", default="")
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    summary = run_eval(
        use_llm=args.llm,
        max_pages=args.max_pages,
        max_pdfs_per_exp=args.max_pdfs_per_exp,
    )
    report = format_report(summary)
    print(report)
    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
        print(f"\nInforme: {args.report}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
