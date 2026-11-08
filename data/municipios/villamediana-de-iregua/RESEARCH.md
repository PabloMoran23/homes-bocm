# Villamediana de Iregua — INE 26168, La Rioja

Verified on 2026-11-08 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Exactly one municipal adapter; scheduled ingestion, granted licences and missing
coordinate jitter are disabled. This is a partial document-inventory snapshot,
not a consolidated statement of planning law currently in force.

## Official source discovery

- Municipal normative inventory: https://villamedianadeiregua.org/index.php/normativa
  links directly to **PLAN GENERAL MUNICIPAL**. The municipal page identifies
  Villamediana de Iregua, La Rioja; the unrelated Villamediana in Palencia was
  excluded from discovery.
- Extraction root: https://villamedianadeiregua.org/index.php/normativa/category/40-plan-general-municipal
  (HTTP 200). Its PhocaDownload category tree is the source inventory, rather than
  a search-engine selection of notices. The adapter traverses its child categories
  and all pagination links. Each document retains its download URL, title,
  PhocaDownload ID, category title and actual listing source URL.
- Categories 41–44: written documentation (11), graphical documentation (46,
  pages at offsets 0/20/40), environmental report (1), CAD drawings (14).
  Category 40 also has the PGM definitive-approval announcement (1).
- Category 47 (I.S.A.) has no direct files, but links to category 48 (written
  documentation, 1) and 49 (graphical documentation, 14). Category 49 links to
  category 50 (noise study, 16). These all belong to the PGM: **104 documents in
  one instrument**, not 104 projects.
- https://villamedianadeiregua.org/index.php/normativa/category/45-modificaciones-del-plan-general
  has the PGM modification number 2 (download 239) and its announcement (256).
- https://villamedianadeiregua.org/index.php/normativa/category/46-planeamiento-de-desarrollo
  has the consolidated modification of the Sector I-9 partial plan (255) and its
  announcement (257). Each of these categories currently describes one instrument,
  represented by one row with two documents. Ambiguous multiple instruments or
  unidentified files in these categories cause failure pending grouping review.

The four derived-instrument PDFs were downloaded into local evidence. Manual
`pdftotext` inspection confirms that announcement 256 concerns PGM modification
number 2, Marianistas parcel boundary: agreement 2016-07-01, BOR publication
2016-07-22. Announcement 257 concerns modification number 1 of the Sector I-9
partial plan, compatibility of uses: agreement 2020-12-17, BOR publication
2021-01-05. These checks establish the document grouping. The parser does not
parse PDFs or hardcode those dates: all emitted date fields and `fase` remain
null. A document headed approval, or an initial-approval draft within a later
approved dossier, must not supply an invented date or phase for every document.

## Scope and exclusions

The live municipal inventory is not complete coverage of subsequent planning.
For example, official BOR notices
https://web.larioja.org/bor-portada/boranuncio?n=anu-568699 and
https://web.larioja.org/bor-portada/boranuncio?n=anu-573248 describe initial
approvals of PGM modifications 8 and 11 in 2025, absent from this tree. They are
research context, not scraped rows. No claim that the municipal tree represents
all modifications, or that its base-plan files are a consolidated current text.

The municipal navigation also exposes PRTR physical-project pages; those are
outside this adapter's deliberately bounded planning scope. The municipal
`https://villamedianadeiregua.sedelectronica.es/dossier.4` link is labelled
**Impresos** and `https://villamedianadeiregua.sedelectronica.es/board/` is a
separate announcement board. Neither has been established as a granted-licence
inventory. No forms, procurement announcements or unrelated news are records.

Documents are linked, not interpreted as machine-readable geometry. No
coordinates, municipal centroids, addresses or approval dates are fabricated.
`lat`, `lon`, `geometry` are null and `publication_ready` is false. Publication
and agreement dates have distinct null fields. Crawl time appears only in the
validation evidence, not as a project date.

## Implementation and validation

The scraper fetches only the reviewed public municipal category tree. Requests
have connect/read timeouts, bounded HTML responses and HTTP status checks.
It follows pagination to exhaustion, deduplicates document IDs, reconciles each
subcategory's declared direct-file count, and rejects missing components,
conflicting identities, unexpected categories, external pagination and excessive
crawl size rather than writing partial output. New files in known PGM categories
are retained; new categories require a grouping review. Updates repeat the full
snapshot since files have no reliable publication watermark. Output is replaced
only after the complete crawl validates. Licence methods return disabled.

- `python -m unittest municipio.test_villamediana_de_iregua -v`: 7 tests passed:
  manifest loading through registry, complete pagination and grouping, null date
  semantics, count mismatch, ambiguous derived grouping, login/navigation-only
  rejection, external pagination rejection and conflicting document IDs.
- Real `VillamedianaDeIreguaAyuntamientoAdapter.backfill_proyectos` run:
  **3 records, 108 linked documents**, with all category totals reconciled.
- Local evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/live/category-*.html`, discovery HTML, derived PDFs and inspected PDF
  text. Validation includes the complete live source URL list and limitations.
- Only the four requested source files are added. Evidence is local and excluded
  from commits. No installation, credentials, external state mutation or publishing.
