# Santanyí — INE 07057, Illes Balears

Verified 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter provides a **partial current website inventory**, not a statement
that the listed instruments are currently approved or that the archive is complete.
Scheduling, missing-coordinate jitter and licence extraction are disabled.

## Official sources

The live municipal inventory is
https://ajsantanyi.net/ca/arxius-i-documents/modificacions-puntuals-nnss
(HTTP 200). It currently advertises three folders:

- [MOD 93 ESMENA DEFICIÈNCIES CIU](https://ajsantanyi.net/ca/arxius-i-documents/modificacions-puntuals-nnss/mod-93-esmena-deficiencies-ciu):
  two ZIP document packages, written documentation and PDF drawings.
- [MOD 94](https://ajsantanyi.net/ca/arxius-i-documents/modificacions-puntuals-nnss/mod-94):
  twelve PDFs: explanatory memorandum, environmental assessment determination,
  nine drawings and executive summary.
- [BOIB NÚM 34, DE 11 DE MARÇ / MP 93 - 94](https://ajsantanyi.net/ca/arxius-i-documents/modificacions-puntuals-nnss/boib-num-34-de-11-de-marc-mp-93-94):
  four PDFs, Catalan and Spanish announcements for each amendment.

All four pages returned HTTP 200 during adapter extraction. The 18 document
links become **two instrument records**, with four links for MP 93 and fourteen
for MP 94. Both language versions remain linked; notices are supporting
provenance, not separate projects, procurement awards or granted licences.

For independent source checking, the Catalan BOIB PDFs were downloaded and
converted using the already installed `pdftotext`, outside the adapter. MP 93
concerns a general road system and the correction of deficiencies. MP 94 concerns
alignment and public-space ordering at Consolació, Gómez Ulla and ronda de na
Ravandella. These are genuine planning instruments, not generic application forms.
The local PDF/text captures preserve those descriptions without hardcoding them
into records extracted from the inventory.

## Date and legal-status semantics

The municipal cards display 10/03/2021 for technical documents and 15/03/2021
for uploaded notices. These are retained **only** as `fecha_web_documento`
on each document, with the page URL that supplied them. They are not approval
or BOIB publication dates.

Manual inspection of the captured BOIB issue 34 shows publication on
2021-03-11 and municipal decisions on 2021-02-22. For MP 93 the decision corrects
deficiencies, with references to earlier provisional approval and an insular
agreement; for MP 94 it is initial approval. The signature is dated 2021-03-09.
These distinct events do not establish today's definitive legal status.
The adapter deliberately does not parse PDF/ZIP bodies: `fecha_publicacion`,
`fecha_acuerdo`, `fecha_aprob`, generic `fecha`, and `fase` remain null. No crawl
date or document upload date is promoted to a legal event.

## Other discovered inventories and limitations

[Revisió Normes Planejament Urbanístic](https://ajsantanyi.net/ca/arxius-i-documents/revisio-normes-planejament-urbanistic)
is a separate municipal archive, checked live with HTTP 200. Its child pages
link to a BOIB PDF, a legacy BOIB URL and two malformed written/graphic ZIP URLs
under `http://libre/www.ajsantanyi.net/…`. This archive is outside the adapter's
explicit NNSS-amendments scope; it is not emitted as an extra record.

The amendment inventory also links to
https://muib.caib.es/mapurbibfront/index2.jsp under “NNSS 1985 i modificacions
posteriors”. This regional viewer is outside this scraper; no complete historical
coverage or geometry extraction is claimed. No verified granted-licence inventory
was established. News, forms, procurement and the regional viewer are not crawled.
No parcel, map point, municipal centroid or inferred geometry is substituted:
coordinates and geometry are null and `publication_ready` is false.

## Extraction and verification

The adapter discovers all folders under the selected municipal root and follows
pagination links on the root and each folder. There was no pagination in the live
snapshot. Rel-next and pager links are supported and tested across both levels;
cycles are deduplicated. Folder counts are checked against unique downloads.
Unexpected folders, unknown notice-to-instrument associations, nested inventories,
foreign pagination, missing content, HTTP failures, excessive pages or response
sizes raise errors before writing a new output. Safety limits fail explicitly
instead of silently truncating. Updates refresh the complete selected inventory.

Only named MOD folders create instruments. MP numbers in BOIB document titles
associate the shared notice folder with those instruments. Stable IDs use the
municipality and actual amendment number, so translated documents and changing
upload URLs do not create additional instruments. Each document retains its title,
URL, source page and displayed web date. HTML is obtained with a bounded streamed
request and a 40-second timeout. Capturing HTML is optional via `capture_dir`.

Validation performed:

- `…/venv/bin/python -m unittest municipio.test_santanyi -v`: six tests passed.
  Tests cover grouping and bilingual provenance, date semantics, navigation/form
  rejection, count mismatches, unknown instruments, pagination at both levels,
  foreign pagination rejection and disabled licences.
- A real live call through `load_manifest('santanyi')` and `load_portal_adapter`
  wrote `evidence/proyectos.jsonl`: **2 actual records, 18 document links**.
- `evidence/validation.json` records `live_records`, all four fetched source URLs,
  limitations, runtime and extraction timestamp. HTML captures and source-URL
  sidecars are in `evidence/captures/`. The two Catalan BOIB PDFs and extracted
  text are in `evidence/boib-mp-{93,94}.{pdf,txt}`. The separate revision inventory
  capture is `evidence/revision-inventory.html`.

Evidence is local and excluded from the four source-file deliverables. No shared
source, dependency, database, credential, deployment or publication changes are
required.
