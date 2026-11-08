# Binissalem — INE 07008, Illes Balears

Verified on 2026-11-07 using the preinstalled Python 3.12 environment at
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts a partial snapshot of real municipal planning instruments.
It does not claim full municipal works coverage or a granted-licence register.

## Official source discovery

The municipal urbanism index:
https://www.ajbinissalem.net/portal-de-transparencia/urbanisme-ok/
links directly to the current inventory and separate pending-instrument and
licence pages. The following pages were retrieved directly over public HTTP:

- https://www.ajbinissalem.net/portal-de-transparencia/instruments-de-plantejament-en-vigor/
  — HTTP 200; a static `main section .content ul.archive` with three PDF links:
  Normes subsidiàries, Modificació puntual núm. 1 and núm. 2.
- https://www.ajbinissalem.net/portal-de-transparencia/instruments-de-plantejament-en-tramit/
  — HTTP 200, “No hi ha entrades”.
- https://www.ajbinissalem.net/portal-de-transparencia/instruments-de-gestio-en-tramit/
  — HTTP 200, “No hi ha entrades”.
- https://www.ajbinissalem.net/portal-de-transparencia/registre-de-llicencies/
  — HTTP 200, repeated heading without usable licence rows. Licences disabled.

Other official discovery results include the municipal works department and
“Llicències d’obres” pages, which list application forms and administrative
procedures. These are not granted licences or physical works records and are
excluded. News and procurement announcements are not used as projects.

## Documents and provenance

All three inventory attachments were downloaded successfully and checked for
PDF signatures during the real adapter run. The exact encoded attachment URLs
and SHA-256 hashes are retained in `documentos`; each document also retains its
inventory provenance in `source_url`. The primary PDF is the record `url` and
`url_documento`; `inventory_url` identifies the municipal listing.

- https://www.ajbinissalem.net/wp-content/uploads/2016/03/nnss.pdf
  — 223,809 bytes. Municipal copy of BOIB no. 49 EXT, 11 April 2008, containing
  the NNSS material. The PDF includes other bulletin text, which is not converted
  into additional records.
- https://www.ajbinissalem.net/wp-content/uploads/2018/06/Modificacio%CC%81-puntual-nu%CC%81m.-1.pdf
  — 608,043 bytes. The cover identifies the municipal NNSS modification,
  “Memòria i normes urbanístiques” and “Aprovació provisional”. It concerns
  golf-course uses in rural land. Its background refers to the original NNSS
  approval and publication; those dates do not establish this modification's
  approval date.
- https://www.ajbinissalem.net/wp-content/uploads/2018/06/Modificacio%CC%81-puntual-nu%CC%81m.-2.pdf
  — 18,787,940 bytes. Linked by the municipality as modification no. 2; local
  `pdftotext` provides no usable text. No OCR or phase inference is performed.

Important discrepancy: the inventory labels the collection “en vigor” but the
modification 1 document is a provisional-stage version. `clasificacion_fuente`
records the inventory category, while `fase` remains null for all records. This
is a document inventory, not an independent verification of current legal force
or of consolidated planning provisions. No final approval is inferred.

## Parser and scope

The parser requires the actual page heading and archive container. It recognizes
NNSS and numbered modifications, groups documents with the same instrument
identity, retains every distinct attachment link and deduplicates repeated URLs.
Unicode accents and decomposed filenames are handled without changing the
server's file paths. Identities use municipal instrument identifiers, not crawl
dates. Sidebar links never become records. An unrecognized archive entry, empty
archive, unexpected document host or changed page structure raises an error.

The reviewed inventory is a single static list without pagination. The adapter
rejects pagination links/markup for review instead of silently stopping at a
first page. There is no maximum row count or sliced result list. Every listed
attachment is verified before atomic output replacement; a failed attachment
leaves previous output intact. HTML is bounded at 2 MB and PDFs at 40 MB, with
explicit errors on overflow. Updates refresh the complete inventory snapshot.

Publication, agreement and approval dates are separate null fields: no date is
extracted from this inventory, upload directories, PDF stamps or crawl time.
No coordinates or geometry are supplied by the parsed inventory. `lat`, `lon`
and `geometry` remain null, `publication_ready` is false, scheduling and missing
coordinate jitter are disabled. There is no geographic coverage claim beyond
municipality identity and no complete historical inventory claim.

## Validation and local evidence

- `python -m unittest municipio.test_binissalem -v`: seven tests passed. They
  cover real instrument recognition, unknown date semantics, grouping and link
  retention, decomposed Unicode URLs, pagination rejection, exclusion of
  forms/navigation, disabled licences, manifest loading and preservation of
  previous output after an invalid attachment.
- Live extraction through `load_portal_adapter(load_manifest('binissalem'))`
  and `backfill_proyectos`: three records, three verified PDF documents.
- Local `evidence/proyectos.jsonl` contains actual extracted records;
  `evidence/validation.json` records source URLs, count, results and limitations.
  `evidence/adapter-captures/` contains the exact HTML and PDFs fetched by the
  adapter, named by URL hash. Discovery HTML, initial PDF captures and local
  `pdftotext` outputs are also under `evidence/`.
- The registry's existing entity-policy annotation currently classifies these
  planning records as documento (3/3), activity_eligible false, because their
  primary URLs are PDFs. This does not establish a granted licence,
  publication eligibility or verified geometry; no shared policy was changed.

Evidence is local and excluded from the source change. Only the municipal
manifest, this research, adapter and parser test are added. No dependency,
shared code, database, deployment or git metadata changes are required.
