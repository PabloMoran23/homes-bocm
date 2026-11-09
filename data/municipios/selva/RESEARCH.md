# Selva — INE 07058, Illes Balears

Verified live on 2026-11-09 using the preinstalled batch virtualenv. This adapter
covers two real municipal planning instruments, not granted licences or a complete
inventory of public construction projects. Scheduling is disabled.

## Official source discovery

- https://ajselva.net/ca/ajuntament/departament-durbanisme — HTTP 200. The current
  urbanism department page explicitly says Selva has no municipal general planning
  and links the PDSU, protected-elements catalogue and paths catalogue. This does
  not mean there are no specific planning instruments. General legislation, licence
  guidance and application procedures on this page are not extracted as records.
- https://ajselva.net/ca/arxius-i-documents/projecte-de-delimitacio-del-sol-urba-0
  — HTTP 200. Official PDSU inventory. Complete traversal of 9 HTML pages found
  32 distinct attached file URLs: memory, regulations, cartography, BOIB notices,
  error correction and allegations material. One instrument, not 32 projects.
- https://ajselva.net/ca/arxius-i-documents/cataleg-delements-i-espais-protegits-del-terme-municipal-de-selva
  — HTTP 200. Official protected-elements catalogue. Complete traversal of 14
  HTML pages found 57 distinct file URLs, including normative text, category
  inventories, cartography and notices. Individual protected properties are not
  emitted as construction projects.
- https://ajselva.net/ca/cataleg-de-camins (department link `/node/5793` redirects
  here) — HTTP 200. Five PDF links, including an 86.4 MB catalogue. Discovered and
  captured, but outside this adapter's two-instrument scope. No claim to complete
  paths, all works, historical planning, procurement or electronic-board coverage.

## Date semantics and document provenance

The runtime reads HTML document inventories and follows every nested folder and
file-description page, retaining actual attachment titles, URLs and their origin
pages. Documents are deduplicated within each instrument, retaining all source
pages. Parent folder badges count child nodes, not all descendant PDFs: the PDSU
memory folder says one document while its child exposes two PDFs. Counts are
therefore established by traversing the complete tree, not by trusting badges.

BOIB dates explicitly present in attachment titles become document-level
`fecha_publicacion_boib`. Upload/display dates such as 03/08/2026 are not used as
publication, agreement or approval dates. Instrument-level `fecha`,
`fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` and `fase` remain null: the
runtime does not parse the legal narrative inside PDFs or choose a single date
from several notices and corrections.

For manual corroboration, two actual municipal-hosted BOIB PDFs were downloaded
and converted with the preinstalled `pdftotext` into local evidence:

- `boib-0.pdf`: BOIB 103, 2020-06-06, notice 4426, definitive PDSU approval.
  The narrative states the plenary agreement was 2020-05-12. The municipal copy
  resides in a `2026-08` upload directory; that is not the approval year.
- `boib-1.pdf`: BOIB 175, 2020-10-13, notice 9604, **correction** of the catalogue's
  definitive-approval publication. It reproduces the 2020-05-12 agreement and
  identifies the original BOIB 103 publication on 2020-06-06. The correction date
  must not be interpreted as the original approval date.

These corroborations establish genuine instruments, but are not hardcoded dates
in the scraper. The PDFs contain original CAIB provenance URLs as well as the
municipal source copies retained in the extracted records.

## Coverage and failure behaviour

Every extraction fully refreshes both configured document trees. There is no
incremental date filter. Numeric/next pagination is rejected explicitly instead
of silently truncated. Missing headings, empty leaves, unexpected document hosts,
changed root identities, HTTP errors and excessive page/response limits fail the
run before replacing the previous JSONL output. HTML captures may be written via
optional `capture_dir`; that local setting is not required in the manifest.

The runtime preserves all linked PDFs, but does not download or parse all their
contents. No usable vector geometry is extracted from the cartographic PDFs.
Latitude, longitude and geometry remain null; `publication_ready=false` and
`geocode.jitter_missing=false`. No centroid or invented approval date is used.
Licences remain disabled; no public granted-licence inventory was verified.

## Reproduction and results

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_selva`: 6 tests passed, covering grouping,
  provenance, bulletin versus upload dates, pagination rejection, navigation/form
  exclusion, external attachment rejection, manifest loading and disabled licences.
- Live extraction used `load_manifest('selva')`, `load_portal_adapter(manifest)`
  and `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, with
  `manifest.portal.config['capture_dir']='evidence/captures'` set locally before
  loading the adapter. Result: 2 genuine instruments, 89 retained document URLs,
  23 fetched HTML pages; standard entity-policy annotation reports status ok
  (both categories unknown; not assumed to be residential projects).
- `evidence/validation.json` contains `live_records`, the complete `source_urls`,
  limitations and extraction report. `evidence/proyectos.jsonl` contains the live
  output. `evidence/captures/` filenames are the first 20 hex characters of the
  SHA-256 of each requested URL plus `.html`. Discovery HTML and the two BOIB
  PDF/text captures are also under `evidence/`. All evidence is local, uncommitted.

Only the four requested source files are added. No dependencies or shared sources
are changed, and no publishing or external state mutation is performed.
