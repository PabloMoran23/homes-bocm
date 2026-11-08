# Artà — INE 07006, Illes Balears

Verified live on 2026-11-08 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts real planning instruments from the current municipal
inventory. It does not claim complete municipal coverage, a consolidated legal
text, physical works execution status, or granted licences.

## Official source discovery and scope

The official [Planejament i normativa urbanística inventory](https://www.arta.cat/ajuntament/fitxaServeis.php?id=123)
returned HTTP 200. It links the base Normes subsidiàries, numbered modifications
2–7, heritage and path catalogues, s'Estanyol reparcellation, Son Tallet
compensation-board statutes and general municipal agreements. The implemented
scope is the base NS and every numbered modification linked in that inventory.
The other categories are expressly outside coverage. No news, procurement,
application forms, or general licence-policy agreements become records.

Live sources fetched by the adapter:

| Instrument | Official detail source | Result |
| --- | --- | --- |
| Normes subsidiàries | https://www.arta.cat/ajuntament/article.php?idart=167 | 35 document links |
| NS correction | https://www.arta.cat/ajuntament/article.php?idart=368 | 3 links grouped into the base NS record |
| Modification 2, Na Pati parking/health use | https://www.arta.cat/ajuntament/article.php?idart=240 | 11 links |
| Modification 3, Colònia de Sant Pere wastewater plant | https://arta.cat/images/DOCUMENTACIO_WEB/MP3NS_EDAR_CSP.pdf | Direct document, HTTP 200 and PDF signature checked |
| Modification 4, funeral use in industrial estate | https://www.arta.cat/ajuntament/article.php?idart=334 | 6 links |
| Modification 5, existing community facilities | https://www.arta.cat/ajuntament/article.php?idart=408 | 6 links |
| Modification 6, water savings | https://www.arta.cat/ajuntament/article.php?idart=492 | 14 links including all three stage subpages below |
| MP6 initial approval | https://www.arta.cat/ajuntament/article.php?idart=450 | Included in MP6 |
| MP6 provisional approval | https://www.arta.cat/ajuntament/article.php?idart=490 | Included in MP6 |
| MP6 complementary provisional approval | https://www.arta.cat/ajuntament/article.php?idart=537 | Included in MP6 |
| Modification 7, PIAT adaptation | https://www.arta.cat/ajuntament/article.php?idart=541 | 6 links |

All HTML source requests returned usable HTTP 200 responses. Original municipal
links use HTTP, www/non-www variants, and an obsolete port 82 for modification 2.
Article requests are canonicalized to HTTPS on www.arta.cat using the published
`idart`; original URLs remain in `source_href` and document URLs. The direct MP3
PDF is fetched over HTTPS, retaining the original published HTTP link.

## Semantics, grouping and provenance

Seven records correspond to the base plan and six modifications. Memories,
regulations, environmental documents, maps, BOIB notices and plenary certificates
are nested in `documentos`, each with its original label, URL and source page.
MP6 approval stages are recursively traversed as documents of one modification,
not separate projects. The CIOTU correction is grouped with the base NS. Its
27/01/2012 heading refers to the earlier agreement being corrected, and is not
assigned as the correction approval date.

For numbered modifications, `fase` comes from the inventory's explicit wording:
2–6 definitive approval, 7 initial approval. The base NS phase remains null.
`phase_evidence` and `detail_headings` retain the municipal wording. MP5 has a
stale detail heading saying initial approval; the inventory says definitive and
the detail includes a BOIB link labelled definitive approval. Both are preserved
rather than silently replacing the contradictory heading.

All record date fields remain null. A dated BOIB issue is publication evidence,
not an agreement date; document labels retain those publication dates without
promoting one of multiple historical document dates to the instrument's date.
PDF contents and signature-verifier targets are not parsed for approval dates.
Linked documents other than the direct MP3 PDF are retained, not individually
downloaded or availability-certified. No coordinate is taken from the municipal
footer's town-hall map. Geometry and coordinates remain null, with
`publication_ready=false` and jitter disabled.

## Completeness and failure behavior

The inventory is a static single page without pagination in the live capture.
Every matching numbered modification is processed; there is no record limit or
first-page truncation. Encountering pagination markup raises an error requiring
review rather than returning an incomplete snapshot. Linked article stages are
visited to completion with cycle detection. The defensive 100-page graph limit
raises an error; it never silently truncates. HTTP errors, unexpected redirects,
missing headings/content/documents, ambiguous base-plan links and oversized
responses also fail before writing results. Update repeats the complete scoped
snapshot. No licence register was verified; both licence methods are disabled.
The schedule is disabled in the manifest.

## Validation and local evidence

- `python -m unittest municipio.test_arta -v`: 5 tests passed. Tests cover scope
  exclusions, document grouping and provenance, old URL canonicalization,
  pagination/login/empty-content rejection, cycles, date/coordinate nulls,
  conflicting phase evidence, preservation of prior output on fetch failure,
  manifest identity and disabled licences.
- Real `ArtaAyuntamientoAdapter.backfill_proyectos` run: **7 records, 82 document
  links**, 12 fetched sources including MP3's verified PDF.
- Local `evidence/proyectos.jsonl` contains the actual records;
  `evidence/validation.json` contains the live count, source URLs, extraction
  timestamp and limitations. SHA256-prefix-named HTML/PDF captures are written by
  the adapter when `config.evidence_dir` is supplied. Discovery captures are also
  retained locally. Evidence is not part of the four source files.
