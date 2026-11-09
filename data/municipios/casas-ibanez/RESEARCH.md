# Casas-Ibáñez — Albacete — INE 02024

Checked live on 2026-11-09. This adapter extracts **one municipal planning
instrument with two linked documents**, not two projects or any granted licences.
It covers the POM documentation currently linked on two municipal pages. It does
not establish the complete legally effective planning instrument or a complete
inventory of works, amendments or planning proceedings.

## Official discovery and document provenance

- https://casasibanez.es/ and https://casasibanez.es/mapa-web/ — HTTP 200.
  The official municipal site map links Normativa Municipal, Instancias, the
  electronic announcement board and the procurement profile. Local discovery
  captures: `evidence/home.html`, `evidence/mapa.html`.
- https://casasibanez.es/normativa-municipal/ — HTTP 200, single static inventory.
  The exact list group “Texto consolidado de las Normas Urbanísticas del Plan de
  Ordenación Municipal” contains the consolidated POM norms. Other groups contain
  tax ordinances and service regulations, which are excluded. In particular the
  cemetery ordinance's 24 November 2023 BOP reference is unrelated to the POM.
- https://casasibanez.es/wp-content/uploads/2024/02/NNUU-consolidado-JUN-2021-1.pdf
  — HTTP 200, PDF, 802193 bytes during research. The inventory's original link is
  HTTP; extraction uses the independently verified HTTPS equivalent and retains
  the original link in `url_enlace_original`. Page 1 identifies the POM of Casas
  Ibáñez, labels this consolidation June 2021, and says it incorporates the
  original document approved in 2001 and subsequent modifications. It explicitly
  describes the publication as informative and not itself legally binding on the
  municipality. Page 2 identifies its scope as Casas Ibáñez (Albacete).
- https://casasibanez.es/instancias/ — HTTP 200, single static inventory. Most
  entries are forms, including licence applications and declarations of works
  and first occupancy. None is evidence of a granted licence. Under “Otros” it
  links “Plano del Municipio. Plano de SU y SUB. Calificación y alturas”.
- https://casasibanez.es/wp-content/uploads/2026/01/Plano-del-Municipio.-Plano-de-SU-y-SUB.-Calificacion-y-alturas.pdf
  — HTTP 200, PDF, 673940 bytes during research. It has no usable text layer.
  A local rendered inspection (`evidence/plano.png`) confirms the legend names
  the Plan de Ordenación Municipal de Casas Ibáñez, urban/urbanizable land,
  classification, qualification and heights, and November 2025. It states that
  the data are informative and cannot be used as an official document. This
  establishes its relationship to the POM, so it is retained in the same record
  as the norms, with its own inventory URL and document role. Its edition is
  different from the 2021 norms; no synchronized legal version is claimed.
- https://casasibanez.sedipualba.es/ — HTTP 200. Identifies Ayuntamiento de Casas
  Ibáñez, P0202400H, and links the board and transparency portal. This supports
  municipal provenance; it is not a project source itself. Capture: `sede.html`.
- https://casasibanez.sedipualba.es/tablondeanuncios/ — HTTP 200. The inspected
  first page explicitly offers seven pages of mixed notices and plenary minutes.
  It was used only for discovery (`tablon.html`), not extraction. No board-wide
  coverage is claimed and no first-page subset is emitted. Extracting works from
  those minutes would require a separate complete crawl and substantive review.
- https://casas-ibanez.transparencialocal.gob.es/ — the sede's linked transparency
  portal failed certificate verification (expired certificate). TLS verification
  was not bypassed. No inventory from this portal is claimed.

## Extraction contract and limits

`CasasIbanezAyuntamientoAdapter` refreshes both complete static HTML inventories
on backfill and update. It requires the expected page headings, exactly one
consolidated-POM list group with documents, and the specifically identified map
link. It preserves every PDF link in that group, deduplicates repeated URLs,
and adds matching map links to the same instrument. Identity is the municipal
POM, independent of upload-path changes. Forms, procurement notices, fiscal
ordinances, ordinary news and navigation links cannot become project records.

Unexpected pagination in these two extraction inventories raises an error;
the adapter does not silently return a page subset. The announcement board's
pagination is outside the declared scope. Missing groups, headings, map links,
nonmunicipal PDF URLs, HTTP failures, unexpected redirects and non-PDF document
responses also fail the extraction before replacing the output. Requests have
timeouts and explicit size limits (3 MB HTML, 10 MB PDF); exceeding them fails
rather than truncating content. Optional `capture_dir` saves both HTML responses
and all fetched PDFs from the actual extraction.

The adapter downloads both linked PDFs to check availability and PDF signature;
it does not parse their approval acts or extract geometry. Document semantics
above were verified during research, using `pdftotext` for the norms and a
rendered view for the map. Changes in the PDF contents require renewed review.

`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` and `fase` are null.
The 2001 approval year, June 2021 consolidation, November 2025 map edition,
upload directories and crawl timestamp do not establish exact agreement or
publication dates. No dates or current approval phase are synthesized from them.
The map is retained as a PDF, with no invented point, municipal centroid or
digitized polygon: `lat`, `lon`, `geometry` are null and `publication_ready=false`.
Scheduling and missing-coordinate jitter are disabled. Both licence methods
return disabled with an empty file and never fetch licence forms.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_casas_ibanez -v`: 10 offline tests passed, covering
  document grouping/provenance, unrelated forms and ordinance exclusion, date and
  geometry semantics, missing and ambiguous source content, external/invalid
  document links, stable identity, pagination rejection, manifest/registry
  integration, snapshot update failure preservation and disabled licences.
- Live extraction uses `load_manifest('casas-ibanez')`, `load_portal_adapter`
  and `backfill_proyectos`, including the existing registry's entity annotation.
  Result: **1 record, 2 documents**. No publication or database steps are run.
  The shared entity policy annotates the instrument `pendiente`,
  `insufficient_identity_evidence`, `activity_eligible=false`: the public
  inventories supply no administrative expediente identifier. The adapter does
  not invent one or override that policy. This is a real planning-document
  inventory candidate for review, not an eligible published activity record.
- `evidence/proyectos.jsonl`: actual live result.
- `evidence/validation.json`: count, source URLs, limitations, UTC check time,
  runtime, parser-test result, discovery outcomes and capture SHA-256 hashes.
- `evidence/live-captures/`: HTML and PDFs fetched by the adapter in that run.
  Additional research captures include the extracted PDF text and rendered map.

Evidence is local and excluded from the four source files to be committed.
