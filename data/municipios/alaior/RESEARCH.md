# Alaior — INE 07002, Illes Balears

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter covers two real planning instruments in the municipality's public
initial-approval dossier. It does not establish their present legal validity or
claim complete municipal project coverage. Scheduling, granted licences and
missing-coordinate jitter are disabled.

## Official source discovery

- https://www.aj-alaior.org/ — HTTP 200, current municipal homepage. Its
  “PG i POD Alaior” link leads directly to the public inventory below.
  Homepage news and procurement links were not treated as project inventories.
- https://alaior.sedelectronica.es/transparency/4c3d0fe8-f28c-4967-abc0-6c4c0d6c7ba7/
  — HTTP 200, titled “7.1.1 APROVACIÓ INICIAL PLA GENERAL I PLA D'ORDENACIÓ
  DETALLADA”. Root contains four BOIB notice links, two instrument folders and
  an reports folder. A suspension-of-licences notice is supporting documentation,
  not evidence of a granted licence.
- https://alaior.sedelectronica.es/transparency/818a8b75-2850-4a10-88d0-46fb5199b108/
  — Plan General: 41 document links, including Spanish/Catalan written documents,
  information plans and ordering plans. One instrument record, not 41 projects.
- https://alaior.sedelectronica.es/transparency/e48d05ac-ef51-47ed-94f1-b604a3d5d9a9/
  — Pla d'Ordenació Detallada: 26 document links in four subfolders.
- https://alaior.sedelectronica.es/transparency/8f9bec50-2b0c-4eac-a0df-f62852ff137f/
  — Two reports concerning both instruments. Both links are retained on each
  instrument together with the four shared notices.
- https://alaior.sedelectronica.es/preview-document/0befc0f8-4488-4f0c-8e08-3a42b9d78981
  — Municipal preview of BOIB 38. The linked PDF was downloaded and its actual
  text read with the already installed `pdftotext`. It states an initial-approval
  plenary agreement of **2022-03-09**, BOIB publication **2022-03-17**, and a
  signature dated **2022-03-14**. Only the first two become agreement/approval
  and publication dates respectively; the signature and crawl dates are not used.
  The PDF itself identifies the bulletin's original location as
  https://www.caib.es/eboibfront/pdf/ca/2022/38/1107277 (not separately fetched).

Web search surfaced the regional MUIB viewer, historical planning material,
procurement for plan drafting, and licence-related news. Those were discovery
leads, not extracted records. The verified municipal PG/POD inventory provides a
clearer, bounded document collection. No granted-licence register was verified.

## Extraction and pagination

The scraper opens an anonymous public session and discovers each folder via its
current Wicket navigation action. The server supplies a stable transparency URL
in `Ajax-Location`. It recursively visits all instrument subfolders. The PG's
information-plan subfolder initially exposes only 10 of its 15 documents: the
adapter follows the actual “Veure'n més” action and consumes the XML HTML
components until no load-more button remains. It does not execute page scripts.
Each recursive folder's unique document total must match its advertised count;
unknown pagination, cycles, changed markup and count mismatches raise errors.
There is no silent first-page or row-limit truncation.

The live snapshot contains **2 records and 73 unique document URLs**: 41 PG,
26 POD, four shared BOIB notices and two shared reports. The PG record retains
47 links and the POD record 32 links. Each document retains its title, public
preview URL and containing inventory URL. Technical PDFs other than the BOIB
notice are linked, not downloaded or parsed; catalogue entries are not expanded
into separate properties or projects.

`update_proyectos` refreshes this complete bounded snapshot, preserving the two
stable instrument identities. Output is replaced only after all fetches, counts
and date parsing succeed. HTTP requests have timeouts and a checked 10 MB
response limit; reaching a guard fails explicitly. PDF extraction requires the
existing `pdftotext` binary; no packages or dependencies were installed.

## Limits and validation

No verified vector geometry or coordinates were supplied by this extraction.
`lat`, `lon`, `geometry`, and the ambiguous generic `fecha` remain null, and
`publication_ready` is false. This is the published initial-approval dossier,
not an assertion that it supersedes older plans or has since been approved
definitively. Public works, other planning dossiers and licences are outside
this adapter's coverage.

The shared entity-policy wrapper reports both records as `pendiente` because
they lack an extracted numeric municipal expediente reference. No reference was
invented to satisfy that classifier. The output still retains the official
instrument inventory identities, document provenance and the actual published
agreement. This classifier limitation and missing geometry prevent claiming
publication readiness; the local extraction is reviewable.

- Parser tests: `.../venv/bin/python -m unittest municipio.test_alaior -v`:
  **9 passed**, covering date semantics, document grouping, later-page inclusion,
  repeated/unknown pagination, missing sources, count mismatches and manifest flags.
- Real extraction: manifest loaded through `load_portal_adapter`, then
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **2 records**, HTTP
  source captures saved, all 41/26/2 folder counts reconciled.
- Local evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/captures/`, municipal discovery HTML, `boib38.pdf` and its text.
  Captures use SHA-256 URL prefixes as filenames; validation lists fetched URLs
  and coverage limitations. Public Wicket action URLs are session-specific;
  record and document URLs are stable public links.
- Evidence remains local and is not a source deliverable. Only the manifest,
  this research file, adapter and parser test are added as source files.
