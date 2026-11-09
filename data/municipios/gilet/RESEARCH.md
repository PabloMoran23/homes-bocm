# Gilet — INE 46134, Valencia

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Implemented one adapter, covering the Generalitat's published planning archive
for this municipality. This is partial municipal coverage, with no claim that
these instruments remain legally in force or that their works have been executed.

## Source discovery

- https://www.gilet.es and https://www.gilet.es/es/urbanismo: requests failed
  with RemoteDisconnected; the independent web fetch also returned a gateway
  error. No records are extracted from those failed responses.
- https://gilet.sedelectronica.es: HTTP 200, 413-byte redirect/session shell,
  not a usable public licence or project inventory. No authentication attempted.
- [Official municipal planning archive](https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46134%20GILET/):
  HTTP 200, public Generalitat directory index explicitly identifying Gilet and
  province Valencia. It exposes general and deferred planning collections.
  This is the adapter's only extraction inventory.
- [Municipal approval published in the BOP](https://bop.dival.es/bop/downloads?anuncioNumReg=2025%2F15278&lang=es):
  HTTP 200 PDF, independently corroborates archive identifier `46134-1102`.
  Its publication date is 2025-12-23; the council agreement is 2025-06-26;
  registration occurred on 2025-12-09. These three dates mean different things.
  This manual corroboration is not an automated date parser, so the adapter
  leaves **all record dates null**, including this instrument.
- https://ovius.gva.es/oficina_tactica/#/tramita/25054/25269 is the consultation
  service linked by that BOP. Its fetched page is an application shell; it is
  not used as an additional extracted inventory.
- A search result from https://pgou.es/municipio/gilet supplied discovery links
  to the Generalitat archive. That commercial page is not evidence for any
  emitted record, date, coordinate, or validity assertion.

## Observed inventory and grouping

The full live traversal visited **44 directory pages** and retained **89 PDF
links in 10 instruments**. Documents are grouped by the official `46134-NNNN`
archive folder identity, not emitted as separate projects. `registro_id` and
`expediente_grupo` carry that same archive grouping identity;
`referencia_tipo=identificador_registral` makes clear that this is not an inferred
municipal expediente number. Each document retains its original URL, filename,
section and referring directory URL. Record titles preserve the directory title,
including file-year/reference suffixes, without interpreting them as dates.

| Archive ID | Instrument identified by the official folder | Documents |
| --- | --- | ---: |
| 46134-0010 | Interior reform plan, El Ventorrillo | 10 |
| 46134-0020 | Partial plan, sectors 1, 2 and 3 | 20 |
| 46134-0030 | Partial plan, sector S-6 | 1 |
| 46134-0040 | Interior reform plan, sector 9 Camí Convent | 10 |
| 46134-1000 | General plan homologation | 25 |
| 46134-1001 | General plan amendment, non-developable land zone A | 6 |
| 46134-1002 | Amendment concerning attached housing | 3 |
| 46134-1101 | Homologation amendment 3, La Calderona | 6 |
| 46134-1102 | General plan amendment 4 | 4 |
| 46134-2000 | Partial plan amendment, sectors 2–3 | 4 |

## Extraction behavior and limitations

Every descendant directory is traversed, including nested plan-sheet sections.
Apache sorting links and parent links are not records. There is no pagination
in this observed inventory. New next-page controls, unsupported files,
unrecognized instrument folders, mismatched directory headings, failed requests,
redirects or empty instrument groups raise errors. The 500-directory and 2 MB
per-directory guards also fail rather than silently truncate. Updates repeat the
complete snapshot and do not use dates or state-file cutoffs. Output replacement
occurs only after the entire inventory succeeds.

The archive mixes UTF-8 and Latin-1 encoding; the adapter decodes displayed names
but preserves the original percent-encoded link targets. It does not download
or parse PDF contents during normal extraction. A directory called approval
is document provenance, not proof of a definitive approval date or current phase.
No phase, approval date, publication date or agreement date is inferred.

There is no verified feature geometry. PDF plan sheets remain linked documents;
no centroids, jitter or geocoded substitutes are created. Coordinates and geometry
are null and `publication_ready=false`. The manifest disables scheduling,
licences and jitter. Forms, tenders and unrelated news are not scraped. Coverage
excludes a municipal granted-licence register and a complete public-works inventory.

## Validation and local evidence

- `python -m unittest municipio.test_gilet -v`: eight tests pass, covering grouping,
  document provenance, date/geometry null semantics, encodings, multiple instruments,
  pagination/out-of-scope rejection, missing-source failures, full-snapshot update,
  disabled licences and manifest loading.
- Real extraction through `load_manifest('gilet')` and `load_portal_adapter`:
  **10 records, 89 documents, 44 source pages**. Shared entity classification:
  10 referenced instruments, zero unknown entities, status `ok`.
- One document per instrument was additionally fetched for validation: all ten
  returned HTTP 200 and PDF signatures. Their local captures, URLs, sizes and
  SHA-256 hashes are recorded in `evidence/validation.json`. The remaining 79
  document targets are inventoried links, not individually downloaded/validated.
- `evidence/proyectos.jsonl` contains the actual live records;
  `evidence/validation.json` includes counts, limitations, source URLs and the
  capture mapping. `evidence/live-indexes/` contains all 44 live directory
  responses. `evidence/tests.txt` records the successful test run. Discovery
  captures and the independently fetched BOP PDF/text are also local evidence.
- Evidence is local and excluded from source changes. No dependency/shared-source
  edits, credentials, database access, deployment, publishing or git mutations
  were used.
