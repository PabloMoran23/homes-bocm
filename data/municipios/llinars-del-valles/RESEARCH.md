# Llinars del Vallès — INE 08106, Barcelona

Verified live on 2026-11-07 using the preinstalled batch virtual environment.
This adapter covers the complete, currently accessible **Projectes d'obra** page,
which is a small historical inventory, not all current municipal development.
It extracts four genuine physical works from their municipal technical sheets.
`schedule.enabled=false`, `licencias.enabled=false`, and
`geocode.jitter_missing=false`. No verified geometry: `publication_ready=false`.

## Source discovery

- [Municipal urbanism index](https://www.llinarsdelvalles.cat/ajuntament/informacio-oficial/urbanisme-i-medi-ambient/urbanisme)
  identifies separate works, planning and consolidated-PGOU inventories.
- [Projectes d'obra](https://www.llinarsdelvalles.cat/ajuntament/informacio-oficial/urbanisme-i-medi-ambient/urbanisme/projectes-dobra)
  responds HTTP 200 and links four municipal PDF work sheets. Its explicit last
  update is **2016-05-23**, not a publication or approval date of each work. There
  is no pagination in the inspected HTML. All four links are processed.
- [PGOU i instruments planejament](https://www.llinarsdelvalles.cat/ajuntament/informacio-oficial/urbanisme-i-medi-ambient/urbanisme/pgou-i-instruments-planejament)
  responds HTTP 200 but only directs the reader to a generic RPUC entry point,
  `http://ptop.gencat.cat/rpucportal/inici/ca/index.html`. This is not an individual
  project, and neither it nor the page update (2025-01-08) becomes a record.
- [PGOU consolidat (No normatiu)](https://www.llinarsdelvalles.cat/ajuntament/informacio-oficial/urbanisme-i-medi-ambient/urbanisme/pgou-consolidat-no-normatiu)
  responds HTTP 200, with map attachments and an explicit warning that its
  consolidated documentation has informative effect and no official legal
  validity. Its maps are not emitted as separate planning instruments.
- Search discovery also exposed a municipal July 2026 article about provisional
  POUM approval. News and planning-register ingestion are outside this adapter's
  defined works-sheet coverage; it does not claim the 2016 inventory is current
  or comprehensive, or that the POUM has definitive approval.

## Live works and primary documents

| Municipal expediente | Work | Explicit sheet approval | PDF |
| --- | --- | --- | --- |
| 426/2014 | Consolidació estructural de l'edifici annex de Serveis Culturals | 2015-08-31 | [Technical sheet](https://www.llinarsdelvalles.cat/media/repository/documents/urbanisme/projectes-dobra/2016/0303160159_fitxaobra-edifici-annex-serveisculturals.pdf) |
| 524/2013 | Urbanització Pla Parcial Sector D "Can Marquès" | 2014-03-31 | [Technical sheet](https://www.llinarsdelvalles.cat/media/repository/documents/urbanisme/projectes-dobra/2016/0303160108_fitxaobra-urbanitzaciasplaparcialcanmarquaus.pdf) |
| 84/2016 | Ampliació escola bressol Petits Estels | 2016-03-29 | [Technical sheet](https://www.llinarsdelvalles.cat/media/repository/documents/urbanisme/projectes-dobra/2016/2305160110_ampliaciasescolabressolpetitsestels.pdf) |
| 126/2016 | Enderroc de l'edifici de Can Omedes | 2016-05-02 | [Technical sheet](https://www.llinarsdelvalles.cat/media/repository/documents/urbanisme/projectes-dobra/2016/2305160116_enderrocdeledificidecanomedes.pdf) |

All four PDF responses were HTTP 200 and parsed successfully. Original index
links use HTTP; requests use the same municipal host and path over verified
HTTPS, retaining both links. Each record retains sheet text, SHA-256, document
title, source inventory URL and extracted fields. These are technical summaries
issued by the municipal territorial-services area, not approval resolutions.
`fecha_aprob` comes only from the labelled `DATA D’APROVACIÓ` field. The PDFs do
not identify the legal nature of the approval further. Publication and agreement
dates remain null, as does generic `fecha`.

`estado_obra_segun_ficha` preserves the historical execution status from each
sheet. `fase` remains null: no claim is made that those works are still under
construction in 2026. The location is copied as written, including the somewhat
unexpected Sector D location on the cultural-services sheet; it is not corrected
by inference. No coordinates, centroid, jitter or geometry are invented.

## Implementation and failure behaviour

The manifest loads the one municipal adapter through the existing registry.
Requests have timeouts and response-size bounds; unsuccessful HTTP responses,
changed inventory markup, empty lists, unreviewed entries and detected pagination
raise errors before replacing output. The single-page snapshot is fully
refreshed on update; there is no row cap or date cutoff. Supporting documents
are grouped by their actual municipal expediente, retaining all links; conflicting
approval dates fail visibly. Invalid or missing sheet fields are not filled in.

The adapter uses installed requests/BeautifulSoup and the existing system
`pdftotext` executable (Poppler); no package or dependency file was changed.
Missing executable, invalid PDF or unreadable text fails extraction. It does not
use OCR. This executable must also exist on any later execution host.

## Validation and local evidence

Command:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_llinars_del_valles -v`

Eight tests passed: real-content requirement, URL provenance/deduplication,
pagination rejection, explicit approval date variants and invalid dates,
document grouping/date separation, preservation of previous output on failure,
rejection of non-PDF attachments, and manifest/registry integration.

A real `load_portal_adapter(load_manifest('llinars-del-valles'))` extraction
completed with **4 live records**, including the shared registry's entity-policy
annotation. The policy reports three unknown entity categories; extraction does
not override that uncertainty. Local, uncommitted evidence:

- `evidence/proyectos.jsonl`: four actual extracted records.
- `evidence/validation.json`: runtime, test result, live record count, source URLs,
  limitations, record summary and captured-source hashes.
- `evidence/captures/`: the inventory HTML and all four PDFs fetched by the live
  adapter. Initial discovery HTML/PDF/text captures are also under `evidence/`.

Coverage excludes granted licences (no verified register), the complete RPUC,
newer news-only works and municipal history outside this inventory. No credentials,
database, deployment, publishing or Git mutation was needed.
