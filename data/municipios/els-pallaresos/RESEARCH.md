# Els Pallaresos — INE 43100, Tarragona

Verified live on 2026-11-09 with the preinstalled Python environment. One real
planning instrument is extracted: the POUM advance, municipal expediente
93/2026. This is a deliberately partial snapshot, not a complete inventory of
municipal works, historical planning or granted licences. Schedule and missing
coordinate jitter are disabled. No geometry was verified; publication_ready is
false.

## Official source discovery

- https://elspallaresos.cat/ — current municipal website, HTTP 200. Its news
  archive is paginated (40 pages observed); the adapter does not crawl or claim
  coverage of that archive. News, procurement announcements and forms are not
  converted into project or licence records.
- https://seu-e.cat/ca/web/elspallaresos/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — official transparency planning page, inspected through the web reader. Links
  to Generalitat RPUC/MUC rather than exposing a municipal dossier inventory.
  These viewers are outside this adapter's extraction scope.
- https://cido.diba.cat/normativa_local/7305489/planejament-urbanistic-ajuntament-dels-pallaresos
  — Diputació de Barcelona's official planning-publication inventory, HTTP 200.
  The live table contains publications from 2017 through September 2026, including
  modifications of subsidiary rules and special plans. Only the expressly named
  POUM advance row is selected. Other instruments are explicitly outside coverage.
  All table rows are scanned; no pagination was present. Pagination indicators
  cause a failure rather than an incomplete success. Duplicate notice URLs are
  deduplicated and conflicting publication dates rejected.
- https://portaldogc.gencat.cat/utilsEADOP/AppJava/PdfProviderServlet?documentId=1055361&type=01&language=ca_ES
  — official DOGC PDF discovered from that inventory, HTTP 200, DOGC 9760,
  CVE-DOGC-A-26258042-2026. The PDF identifies the municipality, expediente
  93/2026 and the agreement approving the POUM advance and DIE on **2026-07-11**.
  **2026-09-29** is the bulletin publication date, verified independently against
  its header and the inventory. **2026-09-15** is the notice signature date,
  not the agreement date. The instrument is at the advance/public-information
  stage; it is not a definitively approved POUM. The CIDO label "Aprovació
  inicial" is retained in announcement provenance, not used to imply full initial
  approval of the POUM.
- https://elspallaresos.cat/participa/ and
  https://elspallaresos.cat/wp-json/wp/v2/pages/1389 — HTTP 200. Public municipal
  WordPress page/API. The document section is static HTML inside a JavaScript
  shadow.innerHTML template; the adapter parses its literal without executing
  scripts. Five available links are retained: information leaflet, participation
  programme, and reports of three sessions. Disabled advance and DIE cards have
  no available document links and are excluded. Links and titles are source data;
  PDF contents of these participation attachments are not parsed. Their calendar
  is indicative and appears outdated relative to the DOGC notice. Neither page
  creation/modification timestamps nor anticipated calendar dates become approval
  or publication dates.

## Extraction contract and limitations

The adapter downloads the complete CIDO inventory, public participation API
response and each selected DOGC notice. Notice text is extracted with the existing
`/usr/bin/pdftotext`; no software or Python dependencies were installed. Each
response is limited to 8 MB with timeout and HTTP error checking; excess size,
missing expected content, unexpected document provenance, conflicting dates or
multiple POUM expediente identities fail visibly. Stable record identity comes
from the municipality and actual expediente number, not the document title.
Documents and repeat announcements are grouped under the instrument with source
links, announcement text and publication dates retained. Update refreshes this
complete narrow snapshot and atomically replaces output only after validation.

No licence register is asserted. No coordinates, centroid, geometry or approval
dates are synthesized. The five municipal participation document links supplement
the actual instrument established by the DOGC announcement; they are not five
separate projects. The advance memories, plans and DIE mentioned by the DOGC are
not available through the inspected participation cards, so full technical-plan
coverage remains incomplete.

## Validation and local evidence

Executed using `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`:

- `-m unittest municipio.test_els_pallaresos -v`: four tests passed. Tests cover
  agreement/publication/signature separation, bulletin mismatch, unrelated
  content, pagination rejection, duplicate notices, attachment grouping and
  provenance, repeat updates and preserving output after source failure.
- Live `load_manifest` → `load_portal_adapter` → `backfill_proyectos`:
  **1 record**, expediente 93/2026, 7 document links (5 participation PDFs and
  2 official notice representations), entity policy status ok, zero unknowns.
- `evidence/proyectos.jsonl`: actual live record, dates and document provenance.
- `evidence/validation.json`: live_records, source_urls, limitations, runtime
  result and verification timestamp.
- Source captures include `planning-inventory.html`, `participation-page.json`,
  `notice-0.pdf`, and initial discovery captures. Evidence is local only.

Only the municipality manifest, this research note, adapter and parser test are
source additions. No shared source, dependency, database or deployment changes
are required.
