# Argentona — INE 08009, Barcelona, Catalunya

## Official source discovery (2026-11-07)

The municipal Urbanisme page, https://argentona.cat/urbanisme, links directly to:

- https://argentona.cat/document.php?id=63455 — Documents a exposició pública.
  Nine document links, including six project/instrument groups after exclusions
  and grouping the PA-13 reparcel·lació project with its voluntary deed.
- https://argentona.cat/document.php?id=63456 — Documents aprovats.
  Twenty-seven document links. Twenty-two supported project documents; the
  initial/definitive versions of the Puig i Cadafalch junction form one project.
- https://argentona.cat/document.php?id=63457 — current POUM navigation, linking
  to the plan, viewer, judgments and modifications. The older document collection
  https://argentona.cat/poum exposes many PDF plan sheets, regulations and
  catalogues. These are not individual construction projects and are outside
  this adapter's two-inventory scope. The overarching POUM and other modifications
  are not claimed as covered by the two-inventory extraction.

Both implemented inventories return HTTP 200, with ISO-8859-1 HTML. Their
`.document #cos` content contains complete lists, without pagination controls
in the captured responses. There is no configured item limit. A newly introduced
pagination link/container raises an error rather than silently collecting page 1.
HTML captures of the discovery pages and extraction responses are in `evidence/`.

## Scope and semantics

Live extraction: **26 records, retaining 29 project document links** across both
inventories. Projects include the Pumptrack, Can Doro library, street works,
lighting, photovoltaic installations, reservoir rehabilitation, and planning
instruments including the PA-12 POUM modification and PA-13 reparcel·lació.
Inventory membership is evidence of a published municipal document, not evidence
of a granted licence or a completed work.

Exclude the Madà special-contributions financing project, SUD-1 suspension notice,
drought emergency plan, Can Raimí street nomenclature, compensation-board statutes,
standalone PA9 draft deed, and generic verification programme. These are not
physical works projects or the specific planning instruments supported here.
Forms, procurement feeds and news are not used as project or licence sources.
No public granted-licence inventory has been verified; licences remain disabled.

Three explicit, reviewed equivalences group related documents while preserving
original titles, URLs, inventory provenance and title-derived phases:

- Casa Puig i Cadafalch garden: exposed revised text and approved executive project.
- Puig i Cadafalch / Farrero / Mataró junction: initial and definitive projects.
- PA-13 Serra Lladó reparcel·lació: project and voluntary deed. Its urbanisation
  project remains separate; sharing an area does not make two instruments identical.

For other instruments, identity is a hash of the exact municipal document URL.
The reviewed groups have stable descriptive keys. Replacement URLs for ungrouped
instruments can create new identities; this is a current snapshot, not a complete
historical event ledger. Updates refresh both lists in full and replace output
atomically only after all sources parse successfully.

`fase` is populated only from explicit approval wording in a single document
label. Placement in “Documents aprovats” alone does not supply a phase. Grouped
versions keep individual phases and a null aggregate phase, because list position
cannot establish the latest legal status. No overall chronology is inferred.
`fecha`, `fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` stay null: neither
crawl time nor numeric filename prefixes are legal agreement/publication dates.
PDF bodies are not parsed for those dates. Titles remain source text.

Coordinates and geometry stay null. PDF maps are source documents, not verified
machine-readable geometries. No centroid or random coordinates are substituted.
All records have `publication_ready: false`; schedule and geocode jitter are off.
This is partial coverage, not the entire municipal planning/work/licence history.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_argentona -v`: seven tests pass. Tests cover semantic
  exclusions, version grouping, distinct instruments, unknown dates/geometry,
  ISO-8859-1 decoding, failed-source preservation, pagination/login rejection,
  manifest restrictions, snapshot refresh and disabled licences.
- A real call to `ArgentonaAyuntamientoAdapter.backfill_proyectos` using the
  loaded manifest and a local capture directory writes `evidence/proyectos.jsonl`.
- `evidence/validation.json` records live count, source URLs, limitations and
  attachment-check results: all 29 unique links returned HTTP 200 and PDF signatures.
  `evidence/document_checks.json` records HTTP/content
  checks using streamed GETs, without downloading all large project PDFs.
- `evidence/illeta_can_barrau.pdf` is a complete representative municipal PDF
  capture (HTTP 200, application/pdf, 1,391,406 bytes). Document linkage is parsed
  from the municipal inventory; PDF content is not a source of inferred fields.

Evidence stays local. Only the municipality manifest, this research document,
adapter and its parser tests are source changes. No shared code/dependency edits,
credentials, database access, publishing or git mutations are needed.
