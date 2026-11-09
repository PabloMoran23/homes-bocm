# Tauste — Zaragoza — INE 50252

Verified live 2026-11-09 using the preinstalled batch Python runtime.
This adapter extracts a deliberately partial snapshot: **one PGOU texto
refundido, with 27 distinct linked documents**, not 27 independent projects.
Municipal provenance is verified again on every extraction. This is a real
planning instrument; no licence forms, procurement notices, generic service
pages or unrelated news are converted into records.

## Official source discovery

- https://www.tauste.es/urbanismo — HTTP 200. Heading “Plan General de
  Ordenación Urbana de Tauste (Zaragoza)” and a “PGOU TAUSTE” link to
  https://sites.google.com/view/pgoutauste establish municipal provenance for
  the externally hosted document inventory. The municipal page says plans,
  rules and documents can be consulted/downloaded there.
- https://sites.google.com/view/pgoutauste/normas — HTTP 200; explicitly states
  “Texto refundido aprobado en Diciembre de 2018.” Three embedded Drive
  documents: index, general rules and specific rules. The source does not
  specify an approval day, agreeing body, publication date or legal effect.
- https://sites.google.com/view/pgoutauste/planos — HTTP 200; seven linked map
  documents, including municipal classification and urban zoning.
- https://sites.google.com/view/pgoutauste/fichas — HTTP 200; nine linked
  packages of execution-unit, sector, special-plan and detail-study sheets.
  These sheets are components of the PGOU inventory, not evidence of independent
  approval or construction of all the described developments.
- https://sites.google.com/view/pgoutauste/descargas — HTTP 200; ten linked
  packages (report, rules, sheets, catalogue, financial study, maps, consolidated
  report and editable files). Two overlap the embedded rules. Deduplicating by
  actual Drive file ID gives 27 documents; all labels and referring tab URLs
  remain attached to their document.
- https://tauste.sedelectronica.es/board — HTTP 200 in direct Python HTTP
  research. The five displayed notices concern elections, juror lists,
  subsidy rules and financial control; none qualifies as a physical work or
  planning instrument for this extraction. No historical completeness claim.
- https://tauste.sedelectronica.es/transparency/ — HTTP 200 in direct Python
  HTTP research. Its dynamic Wicket tree includes “7. URBANISMO, OBRAS PÚBLICAS
  Y MEDIO AMBIENTE (420)”. That separate tree is **outside the adapter's scope**;
  its 420 entries have not been extracted or classified. This adapter does not
  represent it as empty or complete. The web search/open tool could not access
  the sede pages, but direct HTTP returned the captured public pages.

## Semantics, coverage and operation

Stable instrument identity is `tauste-pgou-texto-refundido`. Every run fetches the
municipal provenance page and all four PGOU tabs before writing a full snapshot.
No row limits or record pagination are applied. The inspected inventory consists
of four static tabs, not a paginated result set. Missing tabs/documents, unexpected
direct tab links, explicit next-page links and unexpected redirects fail the run.
Update uses the same complete snapshot and does not claim an incremental archive.

All 27 published document links are retained under `documentos`, with labels
and source URLs, including embedded index/rules links. Document binaries are not
downloaded or parsed; accessibility of every Drive file, document contents and
legal consolidation/current validity are not certified. The fact that the
municipality currently links this inventory does not establish that every
subsequent amendment has been consolidated into it.

The source's month-only approval statement is preserved verbatim in
`fecha_aprob_texto` and `descripcion`. Exact `fecha_aprob`, `fecha_acuerdo`,
`fecha_publicacion` and generic `fecha` remain null. Crawl time appears only in
validation evidence. No coordinates are inferred from maps, municipal centroids
or addresses: `lat`, `lon`, `geometry` are null and `publication_ready` is false.
Licences, scheduling and jitter for missing geometry are disabled in the manifest.
No verified granted-licence register has been implemented.

## Validation and local evidence

Run with `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`:

- `-m unittest municipio.test_tauste`: six tests pass, exercising grouping,
  embedded links, provenance, missing dates, changed/incomplete pages,
  unexpected tabs/pagination, snapshot output and manifest loading.
- Real `TausteAyuntamientoAdapter.backfill_proyectos` fetched the five source
  pages successfully: 1 instrument, 27 document links, no invented dates or
  coordinates.
- `evidence/proyectos.jsonl` contains the live record;
  `evidence/validation.json` records `live_records`, `source_urls`, limitations,
  document count and verification timestamp. HTML captures of all four tabs,
  the municipal source and the two discovery sede pages are under `evidence/`.
  Evidence is local and must not be committed.

No dependencies or shared sources were changed. No publishing, database access,
repository hosting operations, deployment or pipeline execution was used.
