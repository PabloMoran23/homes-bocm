# Moncofa — INE 12077, Castellón

Verified live 2026-11-08 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This is a partial municipal technical-project inventory scraper, not a complete
planning register, a granted-licence feed or a claim of completed construction.
Scheduling, licence extraction and missing-coordinate jitter are disabled.

## Official inventories inspected

- https://moncofa.com/es/urbanismo/ — HTTP 200. Municipal department page with
  five Elementor accordion sections. Two concern application forms and activity
  procedures; a third holds historic NNSS, amendments and sector planning.
  The last two contain named public-information instruments with substantive
  technical documents. These last two sections are this adapter's scope.
- https://moncofa.com/urbanisme/ — Valencian counterpart discovered in search
  and linked by the Spanish page's hreflang. Not ingested separately, avoiding
  duplicate instruments and differing translation/document inventories.
- https://moncofa.com/es/informacion-publica/ — HTTP 200, captured locally.
  Contains historic consultation headings for Palafangues amendments, NNSS
  amendments, a mosquito ordinance, SPAP rules and a high-voltage occupation
  concession. Some headings contain only a Google consultation form. This mixed
  inventory is not ingested; neither consultation forms nor procurement terms
  establish a granted urban licence. Planning items here can overlap the
  Urbanismo archive, so no independent document-level records are emitted.

## Extracted instruments and document provenance

1. **Finalización urbanización Belcaire Sur**: one urbanisation-project record
   with five documents: municipal decree 2025-4755 and technical volumes I–IV
   (memoria/anejos, planos, conditions and budget).
2. **PAI manzanas 1 y 2 del suelo urbano industrial, polígono Casablanca**: one
   integrated-action-programme record with twelve documents: programme report,
   technical/economic annexes, four urbanisation-project volumes, five labelled
   annexes and reparcelación. These are one instrument dossier, not twelve
   separate projects. The current Spanish page does not label a safety-study
   annex 1; none is invented from the numbering or the Valencian search result.

All 17 labelled PDF URLs were checked live with HEAD: HTTP 200. Two PDFs were
also downloaded and converted with the already available `pdftotext` for manual
source verification: the Belcaire decree confirms submission of the finalisation
project to public information, and the Casablanca programme report identifies
the same two-block industrial execution unit. Captures and document HTTP checks
are in `evidence/`. Exact document URLs and source labels are retained per record
in `documentos`, each with `url_fuente`. Nothing is extracted from news stories.

Several image-only PDF icon anchors in the municipal CMS point to unrelated
Belcaire files inside the Casablanca section. They have no textual document
label and are excluded. The actual named links establish document membership;
repeated URLs are deduplicated within each instrument.

## Dates, status and limitations

`fase` records the page's public-information label. The page remains an inventory;
it does not prove that a consultation is still open, works have been awarded or
executed, or that any licence was granted. Dates in upload paths and filenames
are not publication/approval dates. All record date fields remain null because
the HTML inventory does not explicitly state them. Manual inspection of the
Belcaire decree finds a **09/12/2025 decree/signature date**, which is not a
website publication date or an approval of the works. The adapter does not parse
PDF dates and does not hardcode this date. The Casablanca report's historical
2017 and 2023 agreements concern earlier programming/NNSS decisions and are
not assigned as approval dates to this programme submission.

No coordinates or vector geometry are extracted from PDF plans; no municipal
centroid is substituted. `lat`, `lon`, `geometry` are null and
`publication_ready` is false. Shared registry annotation classifies both records
as `pendiente / insufficient_identity_evidence`, with `activity_eligible: false`:
the inventory supplies named instrument/document identity but no parsed municipal
expediente number. No decree number, scraper ID or related NNSS expediente is
misrepresented as a project expediente to bypass this policy. Review and further
dossier/geometry enrichment are needed before publication as activity.

Historic NNSS, individual planning amendments and other physical works elsewhere
on the website are outside this deliberately narrow implementation. This is a
snapshot of the two technical public-information sections, not full municipal
history. They are fully embedded in one HTML response; there is no pagination
in the inspected source. Next/page/load-more controls cause an explicit error,
as do new unrecognised public-information sections, duplicate instruments,
missing technical categories, empty inventories or changed document origins.
No result-count cutoff or silently truncated pagination is used. Updates refresh
the complete scoped snapshot; failed parsing occurs before output replacement.

## Reproduction and validation

Run from repository root with the runtime above:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
manifest = load_manifest('moncofa')
manifest.portal.config['capture_dir'] = 'evidence'
adapter = load_portal_adapter(manifest)
adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Parser verification: `python -m unittest municipio.test_moncofa -v` — five tests
pass. Tests cover grouping/deduplication, null date/coordinate semantics, rejection
of forms, pagination, changed/incomplete sections and foreign documents, manifest
loading, disabled licences and full-snapshot update behavior. Real extraction
through the manifest/registry: two records, 17 documents, two policy-pending
entities, no fabricated dates or locations. Local `evidence/validation.json`
contains counts, source URLs, limitations and capture hashes. Evidence is local
and is not part of the four source files. No shared code or dependencies changed.
