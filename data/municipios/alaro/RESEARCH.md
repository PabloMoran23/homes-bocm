# Alaró — INE 07001, Illes Balears

Verified with live HTTP extraction on 2026-11-09 using
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter covers the current municipal planning document inventory, not the
complete history of municipal projects, public works or granted licences.

## Official sources discovered

- Municipal urbanism entry point: https://ajalaro.net/ca/hisenda-i-urbanisme/urbanisme
  links to the planning inventory, protected-elements catalogue and related
  information. Licence/application forms are excluded from extraction.
- Planning inventory: https://ajalaro.net/ca/normes-subsidiaries-de-planejament
  separates definitively approved planning from instruments under revision or
  processing. Seven individually named instruments are extracted. The generic
  `Estudis de detall` Drive folder is not an individual instrument and is excluded.
- Written NNSS documents:
  https://ajalaro.net/ca/arxius-i-documents/documentacio-escrita
  contains seven PDF references: agreement, BOIB, regulations and other supporting
  documents. These belong to one NNSS record, not seven projects.
- NNSS maps: https://ajalaro.net/ca/arxius-i-documents/planols contains 22 map PDF
  references, retained with the same NNSS instrument. No geometry is derived.
- UE-1 correction documents:
  https://ajalaro.net/ca/arxius-i-documents/documentacio-correccio-derror-material
  contains four PDF references, grouped under the correction instrument.
  The inventory's `www.ajalaro.net` version returned the municipal home page;
  the verified canonical host without `www` returns the document inventory.
  Municipal document references are normalized to that host.
- Catalogue detail: https://ajalaro.net/ca/cataleg-delements-i-espais-protegits
  explicitly states initial approval on 28.12.2023. It supplements the broader
  inventory's `en revisió/tramitació` classification with `aprobación inicial`.
- Related official inventories/viewers:
  https://ajalaro.net/ca/informacio-relacionada links to MUIB, municipal urbanism
  and IDE viewers, plus territorial and other information. This is reference
  discovery, not additional municipal project records. Those viewer layers are
  outside this adapter's extraction scope.

The municipal HTML sources above returned HTTP 200. Locally saved discovery
captures and extraction captures are under `evidence/`. Public Google Drive
folders linked by the municipality are retained as references with municipal
source provenance; their contents have not been enumerated or authenticated.
No claim is made that every linked PDF or Drive file was downloaded/validated.

## Live coverage and date semantics

| Instrument | Approval explicitly stated | BOIB publication explicitly identified |
| --- | --- | --- |
| NNSS | definitive 2003-10-17 | 2003-11-11 |
| UE-1 material correction | definitive 2006-07-28 | 2006-10-07 |
| EQ-S01 change to sociocultural equipment | definitive 2008-02-15 | 2008-03-08 |
| UE-2, Can Manyoles / former slaughterhouse | definitive 2022-05-27 | unknown |
| Pere Rosselló i Oliver / Son Amengual alignment | definitive 2023-05-05 | unknown |
| Former/current treatment-plant parcels | unknown, in processing | unknown |
| Protected elements and spaces catalogue amendment | initial 2023-12-28 | unknown |

Approval dates come from explicit `A.D.` notation or the catalogue's initial
approval statement. Publication dates come only from explicitly labelled BOIB
references (document title or decoded filename), with a source document URL.
Download-card dates such as 18/03/2025 and 19/10/2022 are upload metadata and are
not used as approval/publication dates. `fecha` and `fecha_acuerdo` stay null;
no distinct agreement date is inferred from an approval label. Dates from PDF
contents are not extracted. Each document retains its discovery source URL.

No real coordinates or vector geometries were verified. All records have null
coordinates/geometry and `publication_ready: false`. No centroid or random
jitter is substituted. Scheduling, licence ingestion and missing-coordinate
jitter are disabled in the manifest.

## Implementation and validation

A complete current snapshot is refreshed on both backfill and update. The live
inventory and three document lists are unpaginated. There is no page-count or
record-count truncation: all listed documents are collected. If pager/next-link
markup appears, extraction fails explicitly pending pagination support. Missing
sections, empty document lists, duplicate instrument identities, unexpected
item types, changed catalogue content, HTTP failures and oversized HTML also
fail instead of writing partial output. All sources are fetched and parsed
before replacing the output. IDs derive from full instrument titles without
approval-date annotations; documents are deduplicated within their instrument.

- `python -m unittest municipio.test_alaro -v`: **7 tests passed**. Tests cover
  document grouping, dates, catalogue enrichment, canonical municipal URLs,
  exclusion of forms/navigation, duplicate rejection, pagination rejection,
  repeat snapshots, failed extraction preserving existing output, manifest
  loading and disabled licence extraction without network calls.
- Direct live `AlaroAyuntamientoAdapter.backfill_proyectos`: **7 records**, with
  32, 5, 1, 1, 1, 1 and 4 references respectively (includes inventory/folder/viewer
  references, not just PDF files).
- Local `evidence/proyectos.jsonl` contains the actual output;
  `evidence/validation.json` records count, source URLs, test result and limitations;
  `evidence/captures/` contains the exact HTML used by live extraction. Earlier
  discovery captures also include the failed `www` response for diagnosis.

Evidence is local and is not a source-code deliverable. No shared code or
dependencies are changed. No publishing, production or database access is needed.
