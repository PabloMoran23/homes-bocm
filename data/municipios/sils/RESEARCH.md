# Sils — INE 17193, Girona

Verified 2026-11-09 with live anonymous HTTP requests. Exactly one adapter covers
one official municipal planning inventory. This is partial municipal coverage,
not a register of granted licences or a claim that all listed instruments remain
in force. Schedule and licence extraction are disabled; missing geometry is never
replaced with a centroid or jitter.

## Source discovery

- [Municipal urbanism index](https://sils.cat/navega/?pagina=3133), HTTP 200,
  links to POUM and “Projectes normatius en curs”. Capture: `evidence/urbanisme.html`.
- [POUM inventory](https://sils.cat/serveis-municipals/urbanisme-2/poum/), HTTP 200,
  is the extraction source. Its complete single-page article has eight instrument
  sections plus the base POUM register dossier: nine records, thirteen document
  links. Captures: `poum.html` (discovery), `poum-live.html` (adapter live run).
- [Municipal normative-project page](https://sils.cat/serveis-municipals/urbanisme-2/projectes-normatius-en-curs/),
  HTTP 200, redirects users by a link to the transparency portal, rather than
  supplying another project inventory. Capture: `normatius-municipal.html`.
- [Transparency normative inventory](https://www.seu-e.cat/ca/web/sils/govern-obert-i-transparencia/accio-de-govern-i-normativa/normativa-plans-i-programes/memories-i-documents-dels-projectes-normatius-en-curs),
  HTTP 200, supplies explanatory text but no instrument/document entries in the
  fetched response. Capture: `normatius.html`. Not treated as evidence of zero
  municipal projects or converted into a project itself.
- [Transparency planning page](https://www.seu-e.cat/ca/web/sils/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic),
  HTTP 200, explicitly links municipal RPUC and MUC queries for **17193**. Its
  2026-07-01 update date describes the web page, not an instrument approval.
  Capture: `planejament.html`. The full RPUC inventory is outside this adapter's
  coverage; the municipality's direct base-POUM dossier 257083 is retained.
- A candidate transparency `urbanisme/projectes-tecnics-221` endpoint returned
  HTTP 404 (`projectes.html`). It contributes no records. No public register of
  granted licences was verified; application forms are excluded.

## Records, grouping and provenance

The adapter reads the article's bold paragraph headings and their following lists.
It emits one record per instrument, retaining every document label and URL with
its municipal index provenance. It handles titles split across multiple strong
nodes. The introductory normative-inventory link is navigation, not a record.
The base POUM is identified by the explicit municipal narrative and official
RPUC detail link, not by inventing a record from a generic search page.

The nine instruments are: Les Comes technical-services POUM modification; Can
Cuca POUM modification; Can Cuca green-zone relocation; Massabè voluntary
reparcelation; Massabè partial-plan modification; Massabè POUM/industrial-parameter
modification; POUM modification in various areas pending approval; industrial
A.7/T500 modification; and the base POUM. Same-place names alone do not establish
that two instruments are the same dossier.

In particular the two Can Cuca sections are distinct:

- The newly linked [Can Cuca document](https://seu-e.cat/documents/2966152/22019835/37225133_25949f25_3_Resum713017142728112744_Censurado.pdf/c733a8a1-9ba7-4d55-9b75-f81a907f1538)
  was downloaded (HTTP 200) as `cuca-resum.pdf`. Its first-page municipal stamp
  states initial approval at the ordinary plenary of 29.10.26.
- The [green-zone relocation agreement](https://sils.cat/media/sites/23/ACORD-DE-PLE-30062021.pdf)
  was downloaded (HTTP 200) as `cuca-acord.pdf`. Its title concerns relocation of
  a green zone, identifies expediente X2021001396 and a plenary on 30 June 2021.
  That instrument's four links stay together. Text captures were made with the
  installed `pdftotext`; they are research evidence, not runtime dependencies.

Runtime extraction reads the HTML inventory, not PDF text. Thus only the explicit
2021 agreement date in the HTML document label becomes `fecha_acuerdo`; the 2026
PDF approval stamp is documented here but not hardcoded in a changing scraper.
`fecha`, `fecha_publicacion` and `fecha_aprob` remain null. Phases are populated
only where the source heading or agreement label explicitly states initial
approval or pending approval; they describe the published stage and do not certify
present legal status. File names, digital-signature and printing dates are never
used as approval/publication dates.

Google Drive files and folders and the Diputació HTTP PDF link are retained
exactly as published. Their contents are not enumerated, their availability is not
claimed, and no credentials are used. The adapter does not claim to have extracted
the entire contents of an external folder. All records have null coordinates and
geometry and `publication_ready=false`.

## Extraction and validation

The request has a 40-second timeout and a 3 MB streaming size bound; exceeding
it raises an error. Missing article/headings, empty or unassigned document lists,
unknown bold sections, duplicate primary documents and detected pagination cause
failure before replacing the output. The reviewed inventory has no pagination;
new pagination must be implemented before accepting it. Update refreshes the full
inventory snapshot; stable identifiers derive from the first source document URL.
An edit/replacement of that primary URL can change identity.

Using `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`:

- `-m unittest municipio.test_sils -v`: five tests passed, covering grouping,
  split title nodes, agreement/publication distinction, missing dates, invalid
  markup/URLs, pagination, unassigned lists, snapshot writing and disabled licences.
- Live `SilsAyuntamientoAdapter.backfill_proyectos` via the loaded manifest:
  status `ok`, **9 records**, **13 retained document links**.
- Local `evidence/proyectos.jsonl`, `evidence/validation.json` and source captures
  contain the extraction, counts, source URLs, timestamp and limitations. Evidence
  is local only and must not be committed.

No shared source, dependencies, registry, database, deployment or git internals
were modified. Acceptance remains for independent review.
