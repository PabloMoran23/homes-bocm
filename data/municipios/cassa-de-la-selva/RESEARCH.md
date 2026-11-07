# Cassà de la Selva — INE 17044, Girona, Catalunya

Verified live on 2026-11-07 using the preinstalled Python 3.12 virtual environment.
One adapter implements a snapshot of the official municipal works inventory.
Scheduling, granted licences and coordinate jitter are disabled. Records have
`publication_ready: false` because no verified project geometry is extracted.

## Official source discovery

- Municipal works page:
  https://www.cassa.cat/index.php/ajuntament/poble-urbanisme/urbanisme-projectes-d-obra
  returns HTTP 200 and embeds the inventory below in an iframe. This establishes
  the repository's municipal provenance rather than relying on a search result.
- Actual works-document inventory:
  https://repo.cassa.cat/urbanisme/projectesobra/ returns HTTP 200 with 26 named
  sections and 64 PDF links. It is a complete static page without pagination.
  The scraper processes every section, producing 25 physical project records and
  retaining all 63 associated PDF links. The single excluded section is
  “Anunci aprovació definitiva d’Estructura de costos del servei d’abastament
  d’aigua i clavegueram 2025”: a service-cost structure, not a physical work.
- Other official inventories discovered, deliberately outside this adapter's
  coverage: the POUM at
  https://cassa.cat/ajuntament/poble-urbanisme/poble-urbanisme-poum and derived
  planning at
  https://cassa.cat/ajuntament/poble-urbanisme/poble-urbanisme-planejamentderivatpoum/poble-urbanisme-planejamentderivatvigent .
  These are separate from the works inventory. Their captured pages and inventory
  links are available in local `evidence/discovery.json`.
- Urbanism procedures:
  https://cassa.cat/ajuntament/poble-urbanisme/tramits-frequeents-d-urbanisme .
  Procedures and application forms are not evidence of granted licences. No
  granted-licence inventory has been verified; licences remain disabled.

## Extraction and provenance

The parser requires the actual `Projectes d'obra` inventory heading and supported
physical-project section titles. Unknown sections, missing PDF groups, unexpected
hosts/paths, absent/conflicting expediente identifiers and pagination cause an
error. It does not emit placeholders or accept a login/navigation page. The
HTTP request has a 40-second timeout and a 2 MB response limit that raises on
excess rather than parsing a truncated response.

Each real expediente is extracted from the source PDF filenames (including the
source's E2024000009 identifier). IDs use this expediente, independent of display
order or title. All documents under a heading belong to that record; repeated
sections with the same expediente merge their document links. URL encoding
preserves actual filenames, accents and apostrophes. Multipart hydraulic works,
capture-of-water phases and the ten solar Cassà 3 studies remain grouped instead
of becoming separate projects. Source titles and each PDF label and URL are
retained. Cassà 3 is a published physical project; its presence does not establish
municipal ownership, permission granted or construction status.

No PDF body is parsed. Record-level publication, agreement, approval and generic
dates, and phase, remain null. Explicit BOP publication dates in individual link
labels are stored only on those documents: the gym's initial and definitive BOP
publications are 2022-12-20 and 2023-03-21, and the cat shelter's definitive BOP
publication is 2026-10-23. Those are publication dates, not agreement dates. A
certificate filename mentioning a plenary meeting is insufficient to establish
an approval date. Crawl times, repository file dates and expediente years never
become approval dates.

Updates refresh the whole inventory; no date cursor drops older or amended
attachments. Coverage is partial at municipality level: other planning
inventories, removed historic entries, granted licences and PDF-body details
are not covered. Document links are retained, but only two sample PDFs have been
downloaded and verified. No coordinates, municipal centroids or jitter are used;
`lat`, `lon` and `geometry` remain null.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_cassa_de_la_selva -v`: 10 tests passed. Tests cover
  grouping, stable source identifiers, document-only BOP dates, cost exclusion,
  pagination rejection, forms/news/procurement rejection, changed-source failure,
  manifest loading, disabled licences, complete refresh and JSONL writing.
- Real extraction through `load_manifest` and `load_portal_adapter`, using
  `backfill_proyectos`: 25 records, 63 retained project-document links; shared
  entity policy reports 25 known expediente records and zero unknowns.
- Two sample PDF requests returned HTTP 200 with `%PDF` bodies: the pool-roof
  certificate and the cat-shelter BOP notice. These corroborate linked document
  availability, without claiming every link was downloaded.
- Local, uncommitted evidence: `evidence/proyectos.jsonl`, `validation.json`,
  `proyectos.entities.json`, `parser-tests.txt`, municipal/index HTML captures,
  `discovery.json` and the two sample PDFs.

Only the four requested source files are added. No shared code, dependencies,
credentials, databases, GitHub, deployment or publication operations are used.
