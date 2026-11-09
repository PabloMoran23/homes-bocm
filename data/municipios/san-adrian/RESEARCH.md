# San Adrián — Navarra — INE 31215

Verified live on 2026-11-09. This adapter covers the complete single-page
**published transparency planning inventory**, not the full contemporary municipal
planning history, works inventory or granted licences. It returns the PGM and
13 separately listed amendments (14 records), each backed by a live PDF.
Scheduling, licence extraction and geocoding jitter are disabled. No coordinates
or geometry are inferred. `publication_ready` is false.

## Official sources and discovery

- https://sanadrian.es/ — HTTP 200, municipal website identifying the Ayuntamiento
  de la Villa de San Adrián (Navarra). Links to its transparency portal.
- https://transparencia.sanadrian.es/ — official municipal transparency portal.
- https://transparencia.sanadrian.es/documentacion/relevancia-juridica/urbanismo-plan-general-municipal/
  — HTTP 200. Explicit PGM narrative, one PGM document and thirteen amendment
  entries. This is the extraction inventory. No pagination was present. The
  adapter processes every `ul.lista-items > li` in the article and refuses
  pagination or changed/unrecognized entries rather than silently truncating.
- PDFs: the inventory links to
  `https://transparencia.sanadrian.es/wp-content/uploads/2016/04/PlanGeneralMunicipal.pdf`
  and `PlanGeneralMunicipal_MOD1.pdf` through `PlanGeneralMunicipal_MOD13.pdf`
  in the same directory. All fourteen returned HTTP 200 and PDF content in the
  actual adapter run. `evidence/validation.json` contains every exact source URL.
- https://sanadrian.es/plan-especial-de-actuacion-urbana-ut-5-calle-el-peso/
  — HTTP 200, later announcement linking the municipal notice board.
- https://sanadrian.sedipualba.es/tablondeanuncios/anuncio.aspx?id=27841
  — HTTP 200, public participation notice for PEAU UT-5, exposed from 2026-10-26,
  with meeting and participation documents. It establishes that later planning
  material exists outside the old transparency inventory. It is **not included**
  in this adapter's coverage, and is not a final approval or granted licence.
- The guessed path https://sanadrian.es/ayuntamiento/urbanismo/ returned 404;
  it is not a data source. Municipal news/category archives are not crawled.

## Record identity, grouping and dates

The parser uses actual inventory entries, not news headlines or navigation.
The plan and each amendment are separate instruments; all links inside an entry
are grouped in its `documentos` array and duplicate links are removed. Repeated
entries with the same primary PDF are consolidated. IDs derive from the primary
source URL, not the list position or a fabricated expediente. Every document
retains its label, inventory URL, exact PDF URL and SHA-256 of downloaded bytes.
PDF metadata from the shared entity policy is preserved; this limited inventory
has no machine-extracted expediente reference and the shared policy classifies
its rows as documents, without claiming activity eligibility.

All thirteen amendment PDFs are scanned pages. They were rendered and visually
reviewed locally to verify that these are distinct real planning amendments:

| File suffix | Instrument/subject visible in the scan |
| --- | --- |
| MOD1 | 1/2011 — UT-2.3, sectors 1, 2, 4, 6, 7 |
| MOD2 | 2/2011 — UE-2, sector 10 |
| MOD3 | 3/2012 — UT-2, sector 7 |
| MOD4 | Orden Foral 4E/2012 — S-14, AR-9, AR-10, UT-7, S.I.1 |
| MOD5 | 5/2012 — sector S-16 |
| MOD6 | 6/2012 — UT-2.1, sector 2 |
| MOD7 | 7/2013 — UT-4, sector S-1 |
| MOD8 | 8/2013 — UT-7, sector S-14 |
| MOD9 | 9/2013 — UT-1, sector 5 |
| MOD10 | 10/2014 — UT-4, sector 3 |
| MOD11 | 11/2014 — article 42, non-developable land |
| MOD12 | 12/2014 — U-3.1, U-3.2, VL-1, VL-2, AR-3, S-9 |
| MOD13 | 13/2016 — URI-2b, sector 3 |

These visual observations are research evidence, not hardcoded scraped records.
The adapter does not OCR or infer these internal references. It retains the
inventory titles verbatim in `source_label`; amendment titles include that label
and the parent PGM name. The MOD3 label says **12 Feb. 2012**, whereas its PDF is
BON 33 of **16 February 2012**, further reason not to interpret label dates.

All semantic date fields remain null. The PGM narrative is preserved as
`descripcion`: it mentions definitive approval by Orden Foral 186/09 of
22 October, its publication in BON 27 on 2010-03-01, and Resolución 149/2010
of 10 February. The actual attached regulations are BON 111 of 2010-09-13.
These are distinct events. Neither crawl timestamps, upload-directory dates,
inventory labels, nor document signature dates become agreement/publication dates.
No approval stage is inferred for an amendment from its date label.

## Implementation and validation

Read the existing manifest loader, portal ABC, registry and municipal examples
before implementation. One adapter implements the four required methods. Updates
refresh the full covered snapshot; they do not claim incremental history.
Requests have timeouts and bounded streaming responses; redirects off the
source host and non-PDF document bodies fail. Output is replaced only after all
linked documents validate, so a document failure preserves the previous JSONL.
Optional `config.evidence_dir` stores the exact inventory HTML and PDFs named by
SHA-256; it is set locally for the verification run, not in the manifest.

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_san_adrian`: 5 tests passed. Covers instrument
  grouping/link deduplication, stable IDs, null date/geometry semantics, forms and
  foreign links, markup failure, pagination refusal, update/disabled licence
  methods, PDF failure preserving prior output, and manifest loading.
- Live `load_portal_adapter(load_manifest('san-adrian')).backfill_proyectos(...)`:
  14 records, 14 downloaded PDFs, all INE 31215, unique record IDs, no invented
  coordinates. Shared entity-policy annotation succeeded, with zero unknowns.
- Local evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/inventory.html`, downloaded PDFs, rendered amendment scans, discovery
  HTML and extracted PGM text. Evidence is local and is not source for commit.

Limitations: historical inventory ending in February 2016, later plans excluded,
no OCR enrichment, no exhaustive register of works or granted licences, no
verified geometry and no assertion of current legal validity for every old
instrument. Forms, procurement announcements and unrelated news are not records.
