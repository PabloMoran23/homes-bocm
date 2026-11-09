# Constantí — INE 43047, Tarragona

Verified live on 2026-11-09 using the preinstalled Python runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The adapter extracts the municipal **approved urbanisation-project inventory**.
It currently yields **one project with 13 document links**, not 13 projects.
This is deliberately partial municipal coverage. Scheduling and licences are
disabled; no geometry is supplied and `publication_ready` is false.

## Official source discovery

- https://constanti.eadministracio.cat/info.0 — HTTP 200. The official electronic
  office links its Urbanisme transparency section directly.
- https://constanti.eadministracio.cat/transparency/51e7fab4-e06d-4db2-a0fe-6f613a0cff00/
  — HTTP 200. Current urbanism inventory; displays 60 items under instruments in
  progress and 113 under definitively approved instruments. These are displayed
  inventory counts, not counts of distinct projects. Also exposes agreements,
  historical planning, other administrations' planning and provisional uses.
- https://constanti.eadministracio.cat/transparency/8d428183-59cf-4ddb-8454-f9851a41c543/
  — HTTP 200. Approved instruments: POUM information/document/map links, POUM
  modifications, partial plans, special plans, urbanisation projects,
  reparcelisation projects, collaborating entities and an expropriation folder.
  The POUM links identify RPUC `codintExp=238296`. These additional sections are
  discovery context and are **not extracted** by this adapter.
- https://constanti.eadministracio.cat/transparency/c093c419-6c40-46b3-bb7b-a79e5dc96654/
  — HTTP 200. The selected approved urbanisation-project inventory currently
  contains one folder: **Projecte d'urbanització del PPU-10 (Exp. 1702/2018)**,
  with an advertised count of 13 documents.
- https://constanti.eadministracio.cat/transparency/c052c094-04a0-4214-a410-df598e3014ea/
  — HTTP 200. That project's folder initially exposes only ten documents and a
  **Veure'n més** control. The public Wicket AJAX response adds three more:
  Pressupost and the BOPT/DOGC publication links. All 13 are retained together.
- https://constanti.eadministracio.cat/preview-document/376d6d8a-7905-4652-9ff6-eefb9fd68d83
  — HTTP 200. A separate live probe confirms the first technical document's
  preview title, PDF format and document creation metadata. Creation time
  `31-jul-2019 13:43:19` is not a publication, agreement or approval date.
- Requests to https://www.constanti.cat and https://web.constanti.cat failed
  with connection closure in this runtime. Search discovery showed municipal
  news, but no news record is used in the extraction. The usable primary source
  is the linked official electronic office, not a search-engine snippet.

## Extraction contract and provenance

The scraper loads the complete selected index and resolves its public Wicket
folder actions in the same anonymous HTTP session. The server returns stable
`/transparency/<uuid>/` folder locations in `Ajax-Location`. No authentication,
private dossier lookup or browser automation is involved. Each project uses its
stable folder URL for identity. The configured inventory can discover additional
named urbanisation-project folders; unrelated folder shapes fail validation.

Within each folder, pagination follows the live **Veure'n més** action until it
is absent. Only XML component HTML is parsed; server-supplied JavaScript is not
executed. Pagination loops, missing components, zero progress and mismatch with
the advertised document count fail before writing output. An unexpected paginated
index raises an explicit error rather than silently omitting projects. The live
run retrieved 10 initial links plus 3 links from one additional page.

The single record retains seven Memòria parts, two Plànols parts, Plecs,
Pressupost and two official announcement links. Document names and URLs are kept
in `documentos`. Technical documents belong to the same urbanisation instrument;
announcements alone cannot produce a project. The municipal expediente
`1702/2018` is taken from the actual folder title, not inferred from publication.

The phase `aprobación definitiva` comes from the official folder hierarchy; it
is not an inferred date or a claim about construction progress. Both announcement
labels explicitly give BOPT/DOGC **06/08/2019**, recorded separately as document
`fecha_publicacion=2019-08-06`. Record-level publication, agreement and approval
dates remain null: the announcement bodies and agreements have not been parsed.
PDF preview links are retained as preview links, not represented as direct PDF
files. No claim is made about full text, execution, procurement award or licences.

`lat`, `lon` and `geometry` remain null. Plans in document form are not verified
vector geometry. No centroid, address geocoding or jitter is substituted. Update
performs a complete snapshot of this section, with the same validation as backfill.

## Validation and local evidence

- `python -m unittest municipio.test_constanti -v`: **8 tests passed**. Covers
  document grouping, distinct date meanings, XML pagination, continuation actions,
  incomplete/repeated links, announcement-only rejection, source structure,
  official-host validation and stable identity.
- Live extraction through `load_manifest('constanti')` and
  `load_portal_adapter(...).backfill_proyectos(...)`: **1 actual record, 13 links**
  (11 technical-document previews and 2 announcements). Shared entity annotation
  reports one classified record, zero unknown records.
- `evidence/proyectos.jsonl` contains the real snapshot;
  `evidence/validation.json` contains the result, source URLs, verification time,
  limitations and preview probe. `evidence/captures/` holds each adapter HTTP
  response including the continuation XML. Discovery captures are also local.
- Evidence is local and is not part of the four source files. No shared code,
  dependencies, deployment or database integration is changed.
