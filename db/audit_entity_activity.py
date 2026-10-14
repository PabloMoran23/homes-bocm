#!/usr/bin/env python3
"""Muestra ciega periódica: evaluar precisión requiere etiquetado humano.

Generación: python db/audit_entity_activity.py --output output/entity-review.json
Evaluación: python db/audit_entity_activity.py --labels output/entity-review.json
"""
import argparse
from datetime import date
import json
from pathlib import Path


def evaluate(rows):
    if len(rows) < 200 or any(type(r.get("identifiable_activity")) is not bool or type(r.get("generic_form")) is not bool for r in rows):
        raise ValueError("Se requieren al menos 200 revisiones completas e independientes")
    accuracy = sum(r["identifiable_activity"] for r in rows) / len(rows)
    forms = sum(r["generic_form"] for r in rows)
    return {"reviewed": len(rows), "precision": accuracy, "generic_forms": forms,
            "passes": accuracy >= .95 and forms == 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/entity-review.json"))
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--seed", default=date.today().isoformat())
    args = parser.parse_args()
    if args.labels:
        report = evaluate(json.loads(args.labels.read_text()))
        print(json.dumps(report))
        return 0 if report["passes"] else 1
    from ingest import connect
    from entity_reprocess import require_policy_active
    with connect() as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            require_policy_active(cur)
            cur.execute("""SELECT kind,id,title,url FROM (
                SELECT 'proyecto' AS kind,id::text AS id,denominacion AS title,enlace AS url FROM homes.proyecto_actividad
                UNION ALL
                SELECT 'licencia',id::text,objeto,COALESCE(raw_json->>'url',raw_json->>'source_dataset') FROM homes.licencia_actividad
                ) sample ORDER BY md5(kind || id || %s) LIMIT 200""", (args.seed,))
            rows = [{"kind": k, "id": i, "title": t, "url": u, "identifiable_activity": None, "generic_form": None} for k, i, t, u in cur.fetchall()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    print(f"Muestra ciega de {len(rows)} candidatos elegibles: {args.output}; requiere verificar publicación y revisión humana")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
