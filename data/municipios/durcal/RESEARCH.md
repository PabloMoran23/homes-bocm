# Dúrcal — Granada — INE 18071

Verified live on 2026-11-09. This adapter extracts a deliberately partial snapshot
of **five named instruments/projects**, grouping **23 municipal document links**
and retaining one regional search reference. It does not assert current legal
validity, approval, execution or granted licences. `publication_ready` is false;
scheduling and coordinate jitter are disabled.

## Official source discovery

The current municipal website https://www.adurcal.com/ returned HTTP 200 using
Python requests and links its transparency service to
https://adurcal.sedelectronica.es/transparency/ . The web browsing service returned
403 on one request to the municipal home page; direct live HTTP access worked.
The anonymous official transparency inventory provides the following section:

https://adurcal.sedelectronica.es/transparency/93d3a21f-0a01-4306-bd0d-4d90df13202c/

It advertises 61 entries under Urbanismo, Obras Públicas y Medio Ambiente: 46
planning documents, 1 environmental-programme document, 0 urban regulations,
1 works/infrastructure document, 0 indicators, 7 public-information documents,
1 agreement document and 5 detailed-planning documents. These are **document
counts, not project counts**. The site exposes public folder navigation through
Wicket action URLs; anonymous requests without the AJAX header follow redirects
to stable `/transparency/<uuid>/` URLs. The adapter reads the action string as
data and uses an anonymous requests session; no JavaScript execution or login.

## Implemented scope and grouping

Parent planning index:
https://adurcal.sedelectronica.es/transparency/358ec28b-a667-4e8c-a86e-3ec5ebdf641e/

- Adaptación parcial a la LOUA de NNSS de Dúrcal:
  https://adurcal.sedelectronica.es/transparency/69b6dcb3-da1c-4135-876c-0b7ccda0b684/
  — all 5 documents grouped (norms, consolidated text, correction, BOP publication,
  plans). The publication document's label alone supplies no publication date.
- Modificación puntual nº 1 del PGOU:
  https://adurcal.sedelectronica.es/transparency/5df32b91-8c7c-4799-bd6b-0b6ef5a76953/
  — 3 explicitly named modification documents grouped. The fourth link, labelled
  PGOU, targets https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf .
  It is a generic regional search, retained in `referencias`; it does not identify
  another specific plan and is not emitted as a separate project.
- Proyecto delimitación casco urbano:
  https://adurcal.sedelectronica.es/transparency/ab2a7382-bc26-443e-8068-b56cae6897cb/
  — all 9 text/plan documents grouped. Infrastructure drawings are attachments to
  the delimitation instrument, not nine separate works.

Parent detailed-planning index:
https://adurcal.sedelectronica.es/transparency/02d78f61-729b-42d3-9d59-fa3ce5582f84/

- Plan Parcial sector SUBS-I-D1 San Blas:
  https://adurcal.sedelectronica.es/transparency/a54539d4-89f5-46d7-a685-050e6b049b6c/
  — all 5 documents grouped: BOP notice, agreement certificate, publication audit,
  newspaper publication and diligenced plan. Filename dates are retained verbatim
  in titles; no approval or publication date is inferred from them.

Public works folder:
https://adurcal.sedelectronica.es/transparency/011ecc97-4b41-48dd-8ec3-eebe477182fa/

- Proyecto viabilidad piscina cubierta — one feasibility project, not a claim of
  construction, procurement award or completed works. The linked official preview
  https://adurcal.sedelectronica.es/preview-document/08d6e4ae-ad29-450c-8457-344cbdfd540f
  was also opened live (HTTP 200). It identifies a PDF and a document creation
  timestamp of 27 January 2021, which is **not** used as an agreement, approval or
  publication date. Its response is captured locally; PDF contents are not parsed.

## Coverage limits and excluded inventories

This is not the entire urbanism inventory, a register of all works, or a claim
that the five instruments are currently in force. No PDF legal interpretation or
geometry extraction is implemented. Dates and `fase` remain null. No municipal
centroid or invented coordinates are supplied; `lat`, `lon`, `geometry` are null.

The following were inspected for discovery but are explicitly outside extraction:

- SNU building inventory (28 files):
  https://adurcal.sedelectronica.es/transparency/e7e8a412-31c6-42fe-afcb-342dfaf95cfe/
  exposes only 10 documents on the first response. It is an existing-building
  inventory, not 28 projects. No rows from this paginated archive are emitted.
- Environmental programmes:
  https://adurcal.sedelectronica.es/transparency/f7be7084-7b71-49a1-80e7-c1a779efa995/
  contains a feline-colony management protocol, excluded as unrelated.
- Public-information projects:
  https://adurcal.sedelectronica.es/transparency/f48f3e68-0fb1-4afd-985e-4a33bc8fb084/
  has 7 documents, including two Nigüelas wind-farm documents, a canine residence,
  solar plant, vehicle facility, an environmental notice and an ambiguously titled
  scanned plan. These require document interpretation, scope checks and grouping;
  none are converted automatically into approvals or granted licences.
- Agreements:
  https://adurcal.sedelectronica.es/transparency/d5864a5f-f710-49e5-a238-f40879fa678c/
  has a generically titled initial public-information notice, excluded pending
  identification of its instrument.
- The sede catalogue and https://www.adurcal.com/solicitudes_instancias/ contain
  application forms. They are not granted licences; licence extraction is disabled.
- https://www.durcal.net/ is a local information site whose footer credits a private
  author. It was not used as official inventory or record provenance.

BOJA search discovery also found historical PGOU approval/subsanación publications
(https://www.juntadeandalucia.es/boja/2009/50/17 and
https://www.juntadeandalucia.es/boja/2020/200/79). These are not ingested or used to
assign legal status or dates to the municipal inventory records.

## Completeness and failure behaviour

For every selected folder the adapter refreshes its parent in the same anonymous
session, reads the live total, resolves the folder and checks that all distinct
links are present. Selected folder totals were 5, 4, 9, 5 and 1. A count mismatch
(including new pagination), nested folder, unknown link, missing identity, changed
pool folder or ambiguous PGOU modification raises an exception before writing
output. Pagination is not silently truncated. Supporting documents have stable
preview URLs and their source titles; IDs derive from canonical instrument-folder
URLs, independent of session tokens or document order. Updates refresh the entire
scoped snapshot; no date-based incremental watermark is fabricated.

## Local validation

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_durcal -v`: 6 tests passed. Covers grouping, distinct
  date semantics, pagination/count mismatch, duplicates, nested folders, login and
  form rejection, public navigation, ambiguous modification and manifest settings.
- Real `load_manifest('durcal')` → `load_portal_adapter` → `backfill_proyectos`:
  5 live records, 23 municipal document links, 1 reference, no fabricated dates or
  coordinates. The existing entity policy annotator reports 5 unknown categories;
  this narrow adapter does not invent project categories to suppress that result.
- `evidence/proyectos.jsonl`, `evidence/validation.json`, and `evidence/captures/`
  contain the actual extraction, source URLs/limitations and HTML captures. Other
  discovery captures are directly under `evidence/`. Evidence is local only.

Only the four requested source files are added. No dependencies or shared source
files are changed; no database, production, publication or deployment is used.
