# Abrera — INE 08001, Barcelona, Catalunya

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts a deliberately partial municipal document inventory. It is
not a licence register or a complete historical inventory. Scheduled ingestion,
licence extraction and geocoding jitter are disabled. `publication_ready=false`.

## Official source discovery

The municipal [Urbanisme — documentació a exposició pública](https://www.ajuntamentabrera.cat/serveis/obres-i-serveis-parcs-i-jardins-urbanisme-i-mobilitat/urbanisme-documentacio-per-a-consulta-publica)
returned HTTP 200 and contains named instruments and their technical PDFs,
annexes, studies and approval notices. This is the implemented source, rather
than procurement results or related news. The live inventory includes documents
whose file names refer to September 2026. File names are not parsed as dates.

Also inspected these official pages (HTTP 200), which are outside this adapter's
explicit single-inventory coverage:

- [Avanç del POUM — Documentació](https://www.ajuntamentabrera.cat/serveis/obres-i-serveis-parcs-i-jardins-urbanisme-i-mobilitat/urbanisme-documentacio-per-a-consulta-publica/avanc-del-poum-documentacio),
  and its duplicate route `/poum/avanc-del-poum/avanc-del-poum-documentacio`:
  informative and justificatory memoranda, agreement certificate and public
  participation material, with a link to `https://poum.abrera.cat/POUM/`.
  This is an advance, not evidence of a definitively approved POUM. The map
  application was not investigated for geometry or scraped.
- [Modified biomass boiler and heat network project](https://www.ajuntamentabrera.cat/serveis/obres-i-serveis-parcs-i-jardins-urbanisme-i-mobilitat/projecte-modificat-a-l-executiu-per-a-la-instal-lacio-d-una-caldera-de-biomassa-i-xarxa-de-calor):
  separate documentation page for the municipal sports facilities. Not included
  in the implemented public-consultation inventory snapshot.

Discovery HTML captures and their URLs are in local `evidence/discovery*`.

## Extracted coverage and grouping

The real adapter run returned **13 instruments**, with **39 document references**:
35 distinct linked PDFs and four distinct embedded PDFs identified by SHA-256.
Every linked PDF was checked with a streaming HTTP GET: all 35 returned HTTP 200
and a PDF signature. These checks validate links, not the legal contents of
all those PDFs.

The records comprise the frontons conservation works; energy transition office;
Can Morral road safety; mobility infrastructure in PI Barcelonès and Sant
Ermengol; Torrent Gran picnic area; forest-fire-prevention delimitation plan;
Can Pous agricultural works; Centre Polivalent roof refurbishment; and five
separate roof safety projects (Casa de la Cultura/Biblioteca, Centre Polivalent,
Escola Bressol Municipal Món Petit, Camp Municipal de Futbol, Escola Ernest Lluch).
Can Pous is a physical works project in public consultation; municipal ownership
or public funding is not asserted.

Documents are grouped by the actual inventory headings, including Can Pous's
heading nested inside the preceding list. The plural roof heading is split by
named equipment. This keeps roof waterproofing and roof safety at the Centre
Polivalent separate. Initial/final notices and technical documents are retained
together. Blank duplicate anchors and identical embedded PDFs are deduplicated.
The stable scraper ID hashes the grouped instrument title; it is **not** a
municipal expediente identifier. A title change can change the scraper ID.

Embedded PDFs have no independent HTTP URL: document references retain the real
source-page URL, embedded SHA-256 and locator; the captured HTML contains the
complete original data URI. The four payloads were also saved as PDF/text
captures locally. Inspection with the existing `pdftotext` confirms that they
refer to the picnic area, roof refurbishment and Casa de la Cultura safety
projects. Runtime extraction does not depend on `pdftotext` or parse PDF text.

## Dates, defects and limits

- All record-level publication, agreement and approval dates remain null. The
  HTML inventory does not state those dates; the adapter does not promote
  document filenames, crawl time, notice signature dates or related-news dates
  to project dates. Approval wording remains in each original document label;
  `fase` stays null because the adapter does not verify the legal effect or
  chronology of the PDFs. Dates visible in manually inspected evidence are not
  hardcoded into the scraper.
- The modified medium-voltage-line burial project has a malformed relative
  link containing its title instead of a document path. The link and reason are
  reported in extraction warnings; the instrument is excluded for lack of a
  usable document. This is one explicit coverage exclusion, not a fake row.
- The Ernest Lluch notice visibly says initial approval while its `title`
  attribute and PDF filename say definitive approval. Both labels/URL are
  retained and a warning is emitted. No approval phase is inferred.
- There is no pagination within the verified inventory block. Related news,
  activities and navigation are outside the parser scope. All inventory
  descendants are traversed; there is no record limit. Detected next-page links
  or pagination widgets cause an error, rather than a truncated successful run.
  New plural groups or unknown roof equipment also fail explicitly for review.
- Requests have timeouts and a 10 MB response limit that raises on overflow.
  Missing/changed headings, empty results and foreign-host redirects fail.
  Updates refresh the complete current inventory; no incremental date cursor
  or historical completeness is claimed.
- No granted-licence register was verified. Licence forms are not grants and
  none are emitted. No coordinates, municipal centroids or geometry are
  invented; all geometry fields are null.
- A live run through the repository registry also invokes the shared entity
  classifier. All 13 title-grouped inventory entries remain
  `pendiente/insufficient_identity_evidence`; its report is `adapter_incident`
  (`unknown_entity_spike`). This downstream eligibility limitation is preserved
  in `validation.json`. No expediente numbers are manufactured to bypass it.
  The records are reviewable documentary project inventories, not approved
  publication output. No shared policy code was changed.

## Validation and local evidence

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_abrera -v`
passed **7 tests**: document grouping and unknown date semantics; nested/split
headings; distinct roof projects and conflicting labels; malformed/duplicate
links; rejection of empty/login/navigation and pagination; embedded-document
provenance/deduplication; manifest integration, disabled licences and refresh.

The final live run loaded `abrera` through `load_manifest` and
`load_portal_adapter`, then called `backfill_proyectos` with capture enabled.
Local, uncommitted `evidence/` contains:

- `proyectos.jsonl`: 13 actual extracted instrument records, with shared entity
  annotations retained.
- `validation.json`: live record count, source URLs, capture hash, timestamp,
  warnings, test count, PDF-link verification counts and coverage limitations.
- `urbanisme.html`: full response, including embedded PDFs.
- `document-checks.json`: status, final URL, MIME type and PDF-signature checks
  for all 35 linked documents.
- `discovery*` and `embedded-*`: supporting source captures.

Only the four Abrera source files were added. No dependencies or shared source
files were changed; no publishing, database, credentials or deployment actions
were used.
