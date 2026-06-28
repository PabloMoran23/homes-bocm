from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from municipio.manifest import list_manifest_slugs, load_manifest
from municipio.orchestrator import run, run_many


def _add_municipio_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--municipio",
        "-m",
        action="append",
        dest="municipios",
        help="Slug del municipio (repetible). Omite para --all-pilot.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Orquestador multi-municipio: licencias y proyectos desde portal del ayuntamiento."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    orch = sub.add_parser("run", help="Ejecutar pasos del pipeline")
    _add_municipio_arg(orch)
    orch.add_argument(
        "--step",
        choices=[
            "all",
            "backfill",
            "update",
            "proyectos_backfill",
            "proyectos_update",
            "licencias_backfill",
            "licencias_update",
            "enrich_geometry",
            "geocode",
            "sync_supabase",
            "validate",
        ],
        default="all",
    )
    orch.add_argument(
        "--pilot",
        action="store_true",
        help="Ejecutar los 3 municipios piloto (mostoles, getafe, pozuelo-de-alarcon)",
    )

    sub.add_parser("list", help="Listar slugs con manifest")

    match_p = sub.add_parser("match", help="Cruzar proyectos del ayuntamiento con BOCM")
    _add_municipio_arg(match_p)
    match_p.add_argument("--pilot", action="store_true")
    match_p.add_argument(
        "--min-score",
        type=float,
        default=0.35,
        help="Umbral mínimo de similitud (0-1, default 0.35)",
    )
    match_p.add_argument(
        "--no-mutual",
        action="store_true",
        help="No exigir que el match sea el mejor en ambas direcciones",
    )

    val = sub.add_parser("validate", help="Solo generar parity-report")
    _add_municipio_arg(val)
    val.add_argument("--pilot", action="store_true")

    q = sub.add_parser("queue", help="Cola de onboarding automático de municipios")
    qsub = q.add_subparsers(dest="queue_command", required=True)
    qsub.add_parser("init", help="Inicializar cola desde web/public/data/summary.json")
    qsub.add_parser("status", help="Estado de la cola")
    qsub.add_parser("next", help="Ver siguiente municipio pendiente (sin reservar)")
    qsub.add_parser("claim", help="Reservar siguiente municipio (in_progress)")
    qdone = qsub.add_parser("done", help="Marcar municipio como completado")
    qdone.add_argument("--municipio", "-m", required=True)
    qdone.add_argument("--pr-url", default=None)
    qdone.add_argument("--notes", default=None)
    qfail = qsub.add_parser("fail", help="Marcar municipio como fallido")
    qfail.add_argument("--municipio", "-m", required=True)
    qfail.add_argument("--error", required=True)

    audit = sub.add_parser("audit-geometry", help="Auditar fuentes GIS de municipios en cola")
    audit.add_argument(
        "--all-done",
        action="store_true",
        help="Auditar todos los municipios con status=done en queue.yaml",
    )
    _add_municipio_arg(audit)

    args = parser.parse_args(argv)

    if args.command == "list":
        for slug in list_manifest_slugs():
            print(slug)
        return 0

    if args.command == "audit-geometry":
        from municipio.geometry_audit import audit_slugs, load_queue_done_slugs, write_audit

        slugs = args.municipios or []
        if getattr(args, "all_done", False):
            slugs = load_queue_done_slugs()
        if not slugs:
            print("Indica --municipio <slug> o --all-done", file=sys.stderr)
            return 2
        path = write_audit(slugs)
        print(json.dumps(audit_slugs(slugs), indent=2, ensure_ascii=False))
        print(f"\nAudit escrito en: {path}", file=sys.stderr)
        return 0

    if args.command == "queue":
        from municipio import queue as qmod

        if args.queue_command == "init":
            qmod.init_from_summary()
            print(json.dumps(qmod.queue_status(), indent=2, ensure_ascii=False))
            return 0
        if args.queue_command == "status":
            print(json.dumps(qmod.queue_status(), indent=2, ensure_ascii=False))
            return 0
        if args.queue_command == "next":
            nxt = qmod.pick_next()
            print(json.dumps(nxt, indent=2, ensure_ascii=False))
            return 0
        if args.queue_command == "claim":
            claimed = qmod.claim_next()
            print(json.dumps(claimed, indent=2, ensure_ascii=False))
            return 0 if claimed else 1
        if args.queue_command == "done":
            entry = qmod.mark_status(
                args.municipio,
                "done",
                pr_url=args.pr_url,
                notes=args.notes,
            )
            print(json.dumps(entry, indent=2, ensure_ascii=False))
            return 0
        if args.queue_command == "fail":
            entry = qmod.mark_status(
                args.municipio,
                "failed",
                error=args.error,
            )
            print(json.dumps(entry, indent=2, ensure_ascii=False))
            return 0

    pilot_slugs = ["mostoles", "getafe", "pozuelo-de-alarcon"]
    slugs = args.municipios or []
    if getattr(args, "pilot", False):
        slugs = pilot_slugs
    if not slugs:
        print("Indica --municipio <slug> o --pilot", file=sys.stderr)
        return 2

    if args.command == "match":
        from municipio.match_bocm import match_many, match_proyectos, write_match_outputs

        if len(slugs) == 1:
            m = load_manifest(slugs[0])
            result = match_proyectos(
                m,
                min_score=args.min_score,
                mutual_best=not args.no_mutual,
            )
            paths = write_match_outputs(m, result)
            out = {k: v for k, v in result.items() if k != "matches"}
            out["paths"] = paths
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            payload = match_many(
                slugs,
                min_score=args.min_score,
                mutual_best=not args.no_mutual,
            )
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.command == "validate":
        if len(slugs) == 1:
            m = load_manifest(slugs[0])
            from municipio import validate as v

            path = v.write_parity_report(m)
            print(json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=2, ensure_ascii=False))
        else:
            from municipio import validate as v

            path = v.write_global_parity_report(slugs, load_manifest)
            print(path.read_text(encoding="utf-8"))
        return 0

    if args.command == "run":
        if len(slugs) == 1:
            result = run(load_manifest(slugs[0]), args.step)
        else:
            result = run_many(slugs, args.step)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    return 0
