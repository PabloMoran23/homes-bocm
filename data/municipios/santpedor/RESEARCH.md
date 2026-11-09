# Santpedor — INE 08192, Barcelona

Verified on 2026-11-08 using anonymous official municipal sources. This adapter
extracts the complete current **Projectes urbanístics** inventory, not a complete
history of municipal planning or works. Live result: **4 records, 8 linked
documents/notices**, grouped by instrument. No granted licences are claimed.
Scheduling and coordinate jitter are disabled; `publication_ready` is false.

## Official sources and scope

- [Projectes urbanístics inventory](https://www.santpedor.cat/regidories-i-serveis/urbanisme/projectes-urbanistics)
  returned HTTP 200. It lists four detail pages, duplicated in mobile and desktop
  widgets. There are no pagination controls or continuation links in the captured
  inventory. The adapter deduplicates these widgets, visits every listed detail
  and fails explicitly if pagination appears. There is no record limit or slice.
- [Ronda Sant Pere to carretera de Callús](https://www.santpedor.cat/regidories-i-serveis/urbanisme/projectes-urbanistics/projecte-per-larranjament-de-calcada-de-la-prolongacio-oest-de-la-ronda-sant-pere-fins-a-la-carretera-de-callus-de-santpedor)
  returned HTTP 200 and links a technical road-repair memorandum and E-TAULER
  notice 596161. The memorandum cover identifies municipal technical services,
  November 2025. That is a document preparation month, not an approval date.
- [Forest-fire delimitation plan](https://www.santpedor.cat/regidories-i-serveis/urbanisme/projectes-urbanistics/pla-de-delimitacio-de-les-urbanitzacions-els-nuclis-de-poblacio-les-edificacions-i-les-installacions-situats-en-terrenys-forestals)
  returned HTTP 200 and links the technical delimitation plan and E-TAULER notice
  591868. Its cover identifies Santpedor, June 2024 and Diputació technical
  offices. Classified as a fire-prevention plan, without implying construction
  execution or land-use approval.
- [Pons Grau, Monjo and Plaça Sant Jordi road repairs](https://www.santpedor.cat/regidories-i-serveis/urbanisme/projectes-urbanistics/projecte-darranjament-dels-carrers-pons-grau-monjo-i-placa-sant-jordi)
  returned HTTP 200 and links a municipal technical memorandum and E-TAULER
  notice 593156. The memorandum cover gives October 2025.
- [Public rural paths memorandum](https://www.santpedor.cat/regidories-i-serveis/urbanisme/projectes-urbanistics/memoria-elaborada-per-larranjament-de-diversos-camins-rurals-de-titularitat-publica-del-terme-de-santpedor)
  returned HTTP 200 and links the memorandum and an announcement PDF. The
  memorandum identifies August 2024, municipal technical services and repairs
  to actual rural paths. The announcement contains an approval agreement and
  expediente X2024003112; its extracted text has missing glyphs, including in
  the introductory agreement narrative. The adapter does not parse PDF dates
  or populate expediente/phase from this manual research.
- [Separate POUM page](https://www.santpedor.cat/regidories-i-serveis/urbanisme/poum)
  returned HTTP 200; it has seven document links and RPUC references for
  modifications 1 and 3. Its prose mentions approval in 2013 and older work on
  a second modification, while the page-update stamp is March 2026. Inspected
  for discovery and captured, but excluded from this adapter's explicit scope.
  No inference about the current legal status of every modification is made.

Every technical PDF and the rural-path announcement returned HTTP 200 with a
PDF signature; all five were downloaded to local evidence. The municipal site
directly links some files on `santpedor.webmunicipal.diba.cat`, its Diputació
hosting domain; those original links are retained, not rewritten. The three
E-TAULER links are retained as notice provenance, without asserting that they
still expose active notices. They are not standalone project records.

## Semantics and extraction safeguards

Only actual inventory entries backed by at least one technical PDF link become
records. Navigation, licence applications, procurement announcements and general
news are not input sources. Unknown entry types, changed article markup, missing
technical attachments and detail-title mismatches raise errors. All document
links within the technical body are retained and deduplicated within their
project, including announcement links. Each document includes its parent
`source_url`; each project includes the inventory and detail URLs. IDs derive
from canonical detail URLs and remain stable across refreshes.

The detail pages expose **page-update dates** (11 March 2026), not project
publication or agreement dates. Only `fecha_actualizacion_pagina` receives these
timestamps. `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` and
`fase` remain null. Neither technical-document preparation months nor crawl
time are substituted for these dates. The adapter reads HTML and retains PDF
links; it does not extract dates, vector geometry or coordinates from the PDFs.
No municipal centroid or invented location is used; `lat`, `lon` and `geometry`
remain null. Availability in this inventory does not assert current execution,
approval or completion status.

Backfill and update both refresh the full inventory. HTTP failures abort the
snapshot, with connect/read timeouts and a 3 MB HTML response limit. Output is
replaced only after all detail pages validate, preserving previous output on
failure. No credentials or sessions are needed.

## Reproducible validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_santpedor -v`: **6 tests passed**, covering
responsive-menu deduplication, grouped document provenance, separate date
semantics, absent geometry, navigation/login/notice-only rejection, pagination
failure, complete refresh and output preservation on a failed detail.

The manifest was loaded with `municipio.manifest.load_manifest`; the configured
`SantpedorAyuntamientoAdapter.backfill_proyectos` performed a fresh live fetch
of the inventory and all four details, writing `evidence/proyectos.jsonl`.
Validation verified four unique records, eight grouped links, INE 08192 and
null approval dates/coordinates. `evidence/validation.json` includes live count,
source URLs, test results and limitations. `evidence/live_sources/` holds the
adapter's exact HTML responses; discovery HTML, five PDF captures, first-page
text extracts and `evidence/document_checks.json` document the research.

Evidence is local and uncommitted. Only the manifest, this research file, adapter
and test module are source additions. No shared source or dependency changes,
publishing, database access or deployment actions are required.
