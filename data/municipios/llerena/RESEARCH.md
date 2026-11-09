# Llerena — INE 06074, Badajoz, Extremadura

Verified live on 2026-11-09 with the preinstalled Python 3.12 virtual environment.
This adapter extracts real planning instruments and a physical public-works
project from three current official document inventories. Coverage is partial:
it is not a historical municipal register, a complete inventory of works or a
register of granted licences. Scheduling and geocode jitter are disabled.

## Sources discovered and reviewed

1. https://www.llerena.org/ayuntamiento/plan-general-municipal/
   redirects to the same path at `https://llerena.org` and returned HTTP 200.
   The bare-host initial probe returned HTTP 403, while the www entry point
   succeeded in both discovery and the real adapter run. The current PGM page
   contains three technical sections (information drawings, planning drawings,
   general documentation). All 227 distinct linked PDFs are retained under **one
   Plan General Municipal record**, including the justification, regulations,
   catalogue and drawings. Section-anchor navigation is excluded. Page metadata
   (2023-10-30) and upload paths (2022/11) are not agreement/publication dates.
2. https://transparencia.llerena.org/urbanismo-obras-publicas-y-medioambiente/plan-urbanistico/
   returned HTTP 200. Its table identifies **Modificación 1/2024**, definitive
   approval, change of designation of the dotational parcel at San Antón nº 3.
   All 11 documents (DOE notice, agreement/annexes, technical documentation and
   drawings) belong to this single instrument. Four links are municipal links to
   public Google Drive files; these retain their exact URLs and are explicitly
   marked as externally hosted. They have not been independently downloaded.
   The anchor text explicitly dates DOE publication to **2025-10-31**. No date is
   inferred from an upload folder or agreement-document filename.
3. https://transparencia.llerena.org/urbanismo-obras-publicas-y-medioambiente/obras-publicas/obras-publicas/
   returned HTTP 200. Its two links are the **project to construct new niches at
   the municipal cemetery, module K**, and its public-exhibition notice. They
   are grouped as one physical public-works project. The technical project is
   linked through Drive. This is a technical project and consultation notice,
   not evidence of contract award, granted licence, completion or execution.

Additional discovery, deliberately outside extraction:

- https://transparencia.llerena.org/urbanismo-obras-publicas-y-medioambiente/plan-urbanistico/modificaciones-plan-general/
  returned HTTP 200 and repeats two of the same modification documents. It is
  not another instrument and is not traversed as another inventory.
- https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37206 returned HTTP 200:
  regional PGM register, showing definitive approval 2022-02-24 and DOE
  publication 2022-07-28. This is a corroborating source, not parsed/enriched
  by this municipal adapter; those dates therefore remain null in the PGM row.
- https://llerena.org/ayuntamiento/documentos-on-line/ and the historic
  https://archivo.llerena.org/ayuntamiento/documentos/index.php were found by
  official-site search to contain application forms. They are not licences
  granted or projects. No usable granted-licence inventory was verified.
- Procurement navigation and general news are not extracted.

## Document verification and date semantics

Local evidence includes downloaded municipal copies of the two official notices,
plus text extracted using the already installed `pdftotext` solely for research:

- `modification-notice.pdf`: DOE nº 210, 2025-10-31, agreement of 2025-07-31,
  definitive approval of modification 1/2024. The narrative also discusses an
  earlier municipal decision subsequently annulled; treating every historical
  date as the current approval would be incorrect.
- `works-notice.pdf`: Badajoz BOP nº 2, notice 5619/2025, 2026-01-05. It describes
  public exhibition of the module K technical project, confirming that the
  project and notice on the works inventory refer to the same work.

The adapter parses HTML inventories, not PDF contents. Only the modification's
explicit DOE anchor label becomes `fecha_publicacion`, with its document URL
recorded in `fecha_publicacion_fuente`. `fecha_acuerdo` and `fecha_aprob` remain
null for every row. The cemetery notice date, although verified manually in its
PDF, is not extracted from a filename or inserted as a hardcoded date. The PGM
has no phase inferred from its document list. The modification's phase comes
from the inventory's explicit definitive-approval text. No generic `fecha` is
used to blur date meanings. No coordinates, centroid or geometry are invented;
all records have null geometry and `publication_ready: false`.

## Crawler boundaries and failure behavior

Each update refetches all three complete pages as a snapshot; there is no
incremental watermark or arbitrary page/record limit. The reviewed inventories
are static, unpaginated HTML. Pagination controls, next-page links, changed
structure, unrecognized documents, duplicate modification references, missing
technical documentation and unexpected redirects raise errors instead of
producing a silently incomplete successful snapshot. The flat works list is
explicitly validated as the reviewed single project/notice pair; a new work
requires extending grouping rather than conflating documents.

Records have stable instrument identities independent of document count or
publication title edits. Links are deduplicated inside their instrument and
retain the originating inventory URL. All source fetches and parsing must
succeed before atomically replacing output. The disabled licence methods write
an empty file without fetching a source. No shared modules or dependencies were
changed.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_llerena -v`: **8 tests passed**. Tests cover
  grouping, stable references, document deduplication and provenance, separate
  date semantics, pagination rejection on every parser, malformed dates,
  form/login rejection, changed works grouping, failed-fetch output preservation,
  manifest/registry loading, refresh and disabled licence behavior.
- Real `load_portal_adapter(load_manifest('llerena')).backfill_proyectos(...)`:
  **3 records**, **240 document links** (227 PGM + 11 modification + 2 works).
  The registry's entity-policy annotation ran successfully; its categories are
  unknown for all three records, as reported in validation evidence.
- `evidence/proyectos.jsonl`: actual live output.
- `evidence/validation.json`: record count, source URLs, timestamp, parser-test
  result, document counts, entity-policy report and explicit limitations.
- `evidence/captures/`: exact live source response bytes, resolved URLs, HTTP
  status and SHA-256 hashes. Other discovery HTML and the two notices are also
  saved under `evidence/`. Evidence is local, excluded from source changes.

No full pipeline, database, deployment, publishing or external write was used.
