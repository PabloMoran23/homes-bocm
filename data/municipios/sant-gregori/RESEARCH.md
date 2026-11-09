# Sant Gregori — Girona — INE 17163

Verified live on 2026-11-09 using the preinstalled batch virtualenv. This adapter
extracts a **partial municipal snapshot**, not all planning history or all public
works. Four genuine records were obtained. Schedule and licences are disabled;
missing coordinates are never jittered. `publication_ready` is false because no
verified project geometry is available.

## Official source inventory and selected coverage

The municipal [urbanism index](https://www.santgregori.cat/ca/arees-municipals/urbanisme-i-habitatge/)
links the following inventories. HTTP GETs of the municipal pages below returned
200; HTML captures are under the job-local `evidence/` directory.

- [Projects at public exhibition](https://www.santgregori.cat/ca/arees-municipals/urbanisme-i-habitatge/projectes-a-exposicio-publica/):
  one named instrument, Pla Parcial Urbanístic SUD 1 Sant Gregori, with a linked
  protected-data PDF and explicit initial approval by the local government board
  on 2025-06-30. This is an initial planning approval, not a granted licence,
  definitive approval, construction completion or publication date.
- [Definitive projects](https://www.santgregori.cat/ca/arees-municipals/urbanisme-i-habitatge/projectes-definitius/):
  two actual construction projects: a greenway from Sant Gregori to Soler i Patel
  and Girona, and connectivity between the Ter and Llémena valley routes. Each
  has its own full project PDF and allegations-response report. These four PDFs
  become two records, each with the council's explicit definitive-approval date
  2021-01-18. No publication date is supplied by this page.
- [POUM](https://www.santgregori.cat/ca/arees-municipals/urbanisme-i-habitatge/poum/)
  and [its document inventory](https://www.santgregori.cat/ca/arees-municipals/urbanisme-i-habitatge/poum/memoria-i-documentacio/):
  one planning instrument, definitively approved by the Girona Territorial Urban
  Planning Commission on 2010-07-21. The specific plan page explicitly cites DOGC
  5841 of 2011-03-21 and links
  [the gazette reference](https://dogc.gencat.cat/ca/document-del-dogc/?documentId=575828).
  That is the recorded publication date. It states entry into force the next day.
  The general urbanism index instead calls 2011-03-22 the publication date;
  this discrepancy is preserved here and in validation limitations. The parser
  uses the specific instrument page, not the overview. All 38 linked PDFs
  (memory, rules, information and ordering maps) and the gazette link are grouped
  under this single instrument. Plain-text document names without links are
  retained in the page capture; no missing URLs are invented.

The linked PDFs are hosted at `docs.hoobaweb.com/1422/`, an external document
hosting service linked directly by the municipal pages. Every extracted document
retains its municipal `source_url`, label and exact resolved URL. PDF contents and
DOGC contents were not independently parsed or verified; project facts come from
the official municipal narratives. Dates are not inferred from filenames, crawl
metadata, search indexing dates or the website footer.

## Discovered but outside this adapter's coverage

- [POUM modifications](https://www.santgregori.cat/ca/arees-municipals/urbanisme-i-habitatge/poum/modificacions/)
  was retrieved and captured as `modificacions.html`. It lists modifications 1,
  1 second phase, 2, 3 and 4, with initial documents and some consolidated texts.
  This separate historical inventory is deliberately not extracted. The base
  POUM record does not imply that these modifications are incorporated into its
  original PDFs, or that its 2010 approval covers them.
- [Transparency public-information inventory](https://seu-e.cat/ca/web/santgregori/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/informacio-publica-185)
  is linked from the municipal public-exhibition page. Search-visible content
  includes older initial, modified, expropriation and definitive versions of the
  greenway projects and modification 4. It is not traversed by this adapter, and
  no completeness over that separate portal is claimed.
- Licence application forms, the procurement section and general news are not
  evidence of granted licences. No usable granted-licence inventory was verified.
  No coordinates, parcel boundaries, geocoded addresses or municipal centroids
  are substituted for project geometry. Linked PDF maps alone are not parsed
  as vector geometries.

## Parser and operational behavior

The four selected pages are static, non-paginated inventories. The adapter reads
all entries and all PDF links within the precise heading/content container,
excluding global menus and the unrelated site-footer donation PDF. It never uses
a result count limit. Pagination controls in that container raise an error rather
than silently returning a first page. Unknown approval entries and unassigned PDF
links likewise fail, making scope changes reviewable. The two allegations reports
are associated through their project names; PDF URLs are deduplicated. A new
project without an explicit approval narrative or document provenance fails.

Network access uses a 40-second request timeout and streamed 4 MB HTML bound.
HTTP errors, unexpected redirects, wrong content types and changed headings fail.
All sources must fetch and parse successfully before the JSONL is replaced.
Updates refresh the complete selected snapshot and keep stable source/title-based
IDs; no cursor or append-only duplication. The licence methods return disabled.

Each record uses `fecha_acuerdo` for the explicit decision date and
`fecha_publicacion` only for an explicit publication date. The POUM also has
`fecha_aprob` for its explicit definitive approval. Generic `fecha` stays null.
Month-only dates stay null; no first-of-month assumption. A phase is the assertion
on the source page, not an inference about subsequent legal status.

## Reproducible validation

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_sant_gregori -v`: **8 tests passed**, including
  instrument/report grouping, POUM document deduplication, date semantics,
  incomplete dates, navigation/forms/news exclusion, pagination and orphan-document
  failure, manifest/registry loading, repeat snapshot stability and preservation
  of prior output on a parse error. Fixtures are synthetic parser inputs, not
  extraction evidence.
- Live run used `load_manifest('sant-gregori')`, `load_portal_adapter`, then
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, with the optional local
  `capture_dir` set to `evidence`. All four pages were freshly fetched by this
  adapter. Result: **4 real records, 44 document links, zero coordinates**.
- Local `evidence/validation.json` records the timestamp, exact source URLs,
  live record count, document counts, tests and limitations. The registry's shared
  entity-policy annotation returned status `ok` but classified all four records
  as category unknown; no categories are fabricated or shared policies changed.
- `evidence/proyectos.jsonl` and HTML captures are local validation artifacts,
  not source files to commit. Only the manifest, this research file, the adapter
  and its test module are added as source files.

No credentials, database access, deployment, publication, dependency installation,
shared source changes or git mutations were used.
