# Sant Climent de Llobregat — Barcelona — INE 08204

Verified live on 2026-11-09. This adapter extracts a deliberately partial municipal
planning inventory: two local MPGM technical packages, not granted licences.
Scheduling and coordinate jitter are disabled. All geometries and coordinates
remain null and every record has `publication_ready: false`.

## Official source discovery

- Municipal urbanism index (HTTP 200):
  https://www.santclimentdellobregat.cat/ajuntament/informacio-oficial/urbanisme
  links to planning in progress, current planning on the transparency portal,
  and Generalitat territorial planning. Captured as `evidence/urbanisme.html`.
- Actual extracted inventory (HTTP 200):
  https://www.santclimentdellobregat.cat/ajuntament/informacio-oficial/urbanisme/planejament-en-tramit
  contains named technical packages and their attachments, not just generic
  service descriptions. Both discovery and adapter-live HTML are captured.
- Current-planning inventory (HTTP 200, redirect to seu-e.cat:443):
  https://www.seu-e.cat/ca/web/santclimentdellobregat/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic-vigent-184
  provides general viewer/normative references rather than an extractable local
  instrument list. Captured as `evidence/vigent.html`. The regional viewers have
  not been exhaustively investigated; no claim of complete RPUC coverage.
- Metropolitan viewer linked there:
  https://geoportalplanejament.amb.cat/AppGeoportalPlanejament2/index.html
  and normative reference:
  https://www.amb.cat/s/web/territori/gestio-i-organitzacio/numamb/index-normes-urbanistiques.html
  are discovery references, not additional extracted records or geometry sources.

## Extracted packages and provenance

1. MPGM i EAE per a l'ordenació dels espais agroforestals a Sant Climent de Ll.
   (`#marcador0`): ten links grouped in one record: technical plan, annexes,
   summary, environmental study, agreement certificate, BOPB, DOGC, newspaper,
   edict board and municipal announcement. The environmental study and annexes
   do not become separate projects.
2. MPGM a l'entorn del Carrer Padró (`#marcador1`): three links grouped in one
   record: technical plan, agreement certificate and DOGC publication. Explicit
   DOGC link label supplies `fecha_publicacion: 2022-03-03` with its source URL.

The adapter retains original document labels and absolute URLs in `documentos`,
uses the technical-plan URL for stable hashed identity, and keeps the exact
inventory anchor as provenance. It requires the inventory heading, technical
MPGM PDF links and an initial-approval statement. Missing/changed source content
fails instead of emitting a placeholder. Navigation and licence forms do not
qualify. Updates refresh the complete supported snapshot. The reviewed inventory
is one page with no pagination; a pagination link causes an explicit error rather
than a silently truncated extraction.

The unheaded industrial-use modification block has suspension-of-licence
certificates/listings/publication only; no technical MPGM package was verified
there, so it is excluded rather than called a granted licence. Regional PDUM,
PMMU 2025–2030 and metropolitan road/parking modification sections lead to general
regional consultation pages and are outside this local technical-package scope.
These exclusions are coverage limitations, not evidence that no other plans exist.

## Dates and legal status

The municipal inventory describes initial approval for both extracted packages;
`fase` records that reported stage, without asserting current legal validity or
that an old public consultation remains open. The page update timestamp is not
an instrument event date. No dates are inferred from filenames or crawl time.

Four linked PDFs (the two certificates and two DOGC notices) were fetched live
with HTTP 200 and application/pdf, and saved under `evidence/`. Local pdftotext
inspection independently confirmed that these are actual planning instruments:

- Agroforestal DOGC 8879, 2023-03-21, reports the council initial-approval agreement
  of 2023-02-28. Notice signature date is 2023-03-14, a distinct date.
- Padró DOGC 8618, 2022-03-03, reports the council initial-approval agreement of
  2022-02-24. Notice signature date is 2022-02-25, a distinct date.

These PDF observations document provenance only. The adapter does not parse PDF
text and therefore leaves `fecha_acuerdo`, `fecha_aprob` and generic `fecha` null.
Agroforestal publication also stays null because its HTML link label has no date.
The Padró publication is extracted from its explicitly dated HTML label, not
mistaken for the agreement/approval date. PDF links are retained for later work.

## Verification and limitations

Runtime used:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_sant_climent_de_llobregat -v`: six tests passed.
  Covers document grouping, date semantics, stable identity, deduplication,
  exclusions, changed markup/stage, pagination refusal and manifest integration.
- Live extraction via manifest loader and registered adapter
  `backfill_proyectos`: two genuine instruments, 13 associated links, entity
  policy validation passed. Both classifications remain unknown under the shared
  entity policy; no residential/development classification is claimed.
- `evidence/proyectos.jsonl` contains actual extracted records;
  `evidence/validation.json` records live count, source URLs and limitations.
  Evidence and PDF/text captures are local and excluded from source delivery.

No exhaustive historical coverage, granted-licence register, verified instrument
geometry or map publication is provided. No municipal centroid or artificial
coordinates are substituted. No credentials, database access, deployments,
shared-source edits or dependency changes were needed.
