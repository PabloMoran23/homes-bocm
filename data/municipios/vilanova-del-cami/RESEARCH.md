# Vilanova del Camí — Barcelona — INE 08302

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Exactly one municipal adapter implements a deliberately partial planning snapshot.
No granted licences are claimed. Schedule and coordinate jitter are disabled.

## Official source inventory

The municipal [Urbanisme inventory](https://www.vilanovadelcami.cat/ajuntament/normativa/urbanisme/)
returned HTTP 200. Its six entries comprise a general agreements directory, three
planning detail pages and two acoustic-map entries. The adapter extracts the three
planning details and excludes the directory and acoustic maps. The live page has
empty pager containers, so all six entries were inspected without pagination.
The crawler follows every pager URL on subsequent runs, deduplicates cycles and
fails explicitly at its 100-page safety limit or unrecognized pagination instead
of writing a truncated snapshot. Each qualifying detail must have documents.

- [PMU r8 Barri Centre](https://www.vilanovadelcami.cat/ajuntament/normativa/urbanisme/pla-de-millora-urbana-sector-pmu-r8-barri-centre.html):
  web publication 2021-07-27; definitive approval by plenary agreement **2021-07-12**,
  parsed from the [attached BOPB notice](https://www.vilanovadelcami.cat/media/repository/temes/Urbanisme_i_obres/PMU_R8/PUBLICACIO_ANUNCI_BOP.pdf).
  The PDF signature date is 2021-07-15 and its gazette imprint is 2021-07-22;
  neither is substituted for the agreement or web publication. Three documents
  (notice, approval certificate, technical plan) form one record. The source
  expediente `PL/2021148` is retained.
- [POUM](https://www.vilanovadelcami.cat/ajuntament/normativa/urbanisme/pla-dordenacio-urbanistica-poum-de-vilanova-del-cami.html):
  web publication 2021-04-09; 18 PDF attachments (DOGC announcement and 17 sector
  plans) plus one unique legacy RPUC URL, grouped under one POUM record. The body
  labels documents with 18/12/2007, 28/06/2016 and 09/04/2021; these untyped link
  dates are preserved in the description, not interpreted as approval dates.
  Both amendment links point to the same legacy `codintExp=281013` URL, so they
  are retained as one unique link and not fabricated as distinct instruments.
  The adapter makes no claim that the page exhausts current POUM amendments.
- [PMU r3 Bonavista detail](https://www.vilanovadelcami.cat/ajuntament/normativa/urbanisme/pla-de-millora-urbana-sector-pmu-r3-barri-de-bonavista-nord-oest.html):
  web publication 2020-05-20. Its heading calls it a plan, but the
  [attached approval notice](https://www.vilanovadelcami.cat/media/repository/temes/Urbanisme_i_obres/PMUr3/Publicacio_ANUNCI_APROVACIO_DEFINITIVA_URBANITZACIO_PMU_R3.pdf)
  explicitly approves the **urbanization project**, by mayoral resolution
  **2020-02-04**, expediente `AP/2019072`. That document determines the extracted
  type and title; the original web heading is retained as `titulo_ficha`, with
  an explicit discrepancy note. The PDF signature 2020-05-18 is not an approval
  or publication date. The notice and technical document form one record.

The inventory also links to the official [RPUC search](https://dtes.gencat.cat/rpucportal/#/consulta/cerca)
and a CIDO municipal planning search. These are discovered pointers, not queried
inventories in this adapter. The [Urbanisme i Obres topic page](https://www.vilanovadelcami.cat/temes/urbanisme-i-obres)
was examined during discovery through web search: it mixes news, services, forms
and planning links. It is not treated as a granted-licence register or a project
inventory. Procurement headlines and unrelated news do not create records.

## Extraction contract and limitations

The adapter refreshes the entire selected inventory on both backfill and update.
Stable IDs hash the municipal detail URL; documents never become duplicate
projects. Requests have a 40-second timeout and 4 MB response cap; errors, invalid
notices, missing content, excessive pagination and zero usable records fail
before replacing the output. Only the two small PMU notices are downloaded and
parsed with the preinstalled `/usr/bin/pdftotext` (30-second subprocess timeout).
No software was installed and no shared dependency file was changed. The large
technical PDFs are linked, not downloaded or interpreted; the same applies to
the POUM attachments and legacy RPUC links. Link retention does not assert their
availability or current validity.

`fecha_publicacion` explicitly means publication of the municipal detail page.
`fecha_acuerdo` and `fecha_aprob` come only from explicit agreement sentences in
the PMU notices, with the notice URL as provenance. Generic `fecha` remains null.
POUM approval and gazette publication dates are not extracted. Page-update
stamps and PDF signature dates are not used. Missing dates remain null.

Coverage is limited to the three instruments exposed by these detail pages,
not all historic/current municipal planning, projects, works or licences.
Neither a municipal centroid nor random coordinate jitter is used: `lat`, `lon`
and `geometry` are null and `publication_ready` is false for all three records.
Map-ready publication would require separate verification of actual geometry.

## Validation and local evidence

- `.../venv/bin/python -m unittest municipio.test_vilanova_del_cami -v`: six tests
  passed. Covers filtered discovery, pagination, source URL guards, grouped
  documents, Catalan dates, document/page discrepancy, distinct agreement dates,
  changed-content rejection and preserving prior output on a failed crawl.
- Real extraction loaded the manifest through `load_portal_adapter` and called
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **3 actual records**,
  document counts **3, 19, 2**, six live source requests, entity-policy status ok
  (one unknown category; no shared classification policy was changed).
- `evidence/validation.json` records `live_records`, exact `source_urls`, runtime
  test command, crawl timestamp, limitations and validation output.
- `evidence/captures/` contains the exact live HTML/PDF responses, named by URL
  hash. Initial discovery pages and notice text captures are also under evidence.
  Evidence is local and is not part of the four source files.
