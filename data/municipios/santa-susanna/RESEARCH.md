# Santa Susanna — INE 08261, Barcelona

Live verification: 2026-11-09. Implemented a municipal planning snapshot using the
public Generalitat RPUC inventory linked by the municipality's transparency site.
Coverage is partial at municipality level: planning instruments only, without a
verified granted-licence register or physical-public-works inventory. Scheduling
and missing-coordinate jitter are disabled. All records have null coordinates
and geometry and `publication_ready: false`.

## Official source discovery

- Municipal transparency planning inventory:
  https://www.seu-e.cat/web/santasusanna/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  returns HTTP 200. It explicitly directs users to the RPUC for municipal planning
  and links `https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08261`.
  The page's update timestamp is not a plan approval or publication date.
- That municipal link redirects to the current public application:
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cercaPublic?reqCode=cerca&municipiSel=08261
  HTTP 200; the HTML itself is an application shell. Its public JavaScript
  identifies the anonymous REST endpoints and parameter semantics used here.
- Live inventory API:
  https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/basica?municipi=08261&idioma=ca&firstRecord=1&rpp=10&sortColumn=codi&sortDirection=asc
  returns `totals: 65`. Pages 1 through 7 return all 65 unique dossier identifiers.
  `firstRecord` is a page number: 0 and 1 both return the first page; 2 returns the
  second. The adapter starts at 1, advances by 1 and validates totals and identity.
- Dossier metadata and full document links:
  https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/detall?codiExpedient=121279&idioma=ca&cercaPublic=false
  returns HTTP 200 with named instrument, municipality, public expediente,
  explicit `dataAprovacio`, `dataPublicacio`, documents and register entries.
  `cercaPublic=false` is the public detail-view parameter in the shipped UI;
  no login, credentials or private endpoint is used.
- The main municipal website (`https://www.stasusanna.cat/`), urbanism inventory
  (`https://www.stasusanna.cat/ca/temes/urbanisme`) and POUM documentation page
  (`https://www.stasusanna.cat/ca/temes/urbanisme/planejament-urbanistic-i-llicencies/aprovacio-provisional-del-pla-dordenacio-urbana-municipal-poum`)
  return HTTP 403 to direct requests in this environment. Search discovery shows
  the latter as provisional-approval documentation from 2023, and the works page
  `https://www.stasusanna.cat/ca/temes/urbanisme/projectes-dobres-municipals/obres-i-licitacions`
  as a service description, not a usable project inventory. Search snippets are
  not extraction inputs. No news item, procurement notice or licence form is
  emitted as a project or granted licence.

## Scope and semantics

The 65-entry filtered RPUC query also contains regional instruments whose primary
municipality is elsewhere, general siting criteria, agreements and a consolidated
urban-area boundary. The adapter retains 50 entries with exact `municipi` equal
to Santa Susanna and planning-instrument types. It excludes 15 other entries:
11 supramunicipal/other-municipality entries, 3 urban agreements and 1 TUC change.
This does not assert that excluded regional plans are irrelevant to Santa Susanna.
The full query is captured before the explicit scope filter is applied.

One record represents one RPUC dossier, with stable ID from its actual numeric
identifier and its official public expediente retained separately. The 1,491
linked documents remain grouped under their dossier, including names, original
metadata, public download URLs, register entries and bulletin references. Plans,
modifications and revisions are distinct instruments; component PDFs do not
become separate projects. No title-derived joining across different dossiers is
attempted. PDF text and geometry are not extracted. One approval PDF (document
148563) was actually downloaded: HTTP 200, application/pdf, 125,873 bytes, PDF
signature verified; this is a sample link check, not validation of every PDF.

Only explicit detail dates populate `fecha_aprob` and `fecha_publicacion`.
Generic listing `data` is deliberately unused; `fecha` and `fase` remain null.
For example, dossier 121279 reports approval 1982-05-26 and publication
1982-08-18. The newer POUM dossier 280920 reports approval 2026-02-03 and
publication 2026-07-17. These are register-reported dates, not crawl dates or dates
copied from historical provisional-approval pages. `vigencia_source` and
`registrat_source` retain the inventory's claims without independently judging
legal currency or asserting that every historical revision remains operative.

Every run refreshes the complete snapshot. HTTP errors, redirects, invalid
payloads, mismatched dossier/municipality, malformed explicit dates, inconsistent
pagination totals, repeated dossiers or premature empty pages fail extraction
before writing an output snapshot. Responses have a 40-second timeout and a
10 MB size limit, which raises an error instead of silently truncating content.
No municipal centroid, inferred coordinates or approval phase is substituted.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_santa_susanna -v`: 5 tests passed. Tests cover
  separate date meanings, missing dates, grouped document links and stable IDs,
  municipality/type exclusions, mismatched details, invalid dates/payloads,
  complete pagination and rejection of truncation, repetition or changed totals,
  manifest loading and disabled licences.
- Actual `SantaSusannaAyuntamientoAdapter.backfill_proyectos` live run: status
  ok, 7 pages, 65 inventory entries, 50 instrument records, 1,491 document links.
- Local uncommitted `evidence/proyectos.jsonl` contains the actual records;
  `evidence/validation.json` contains live counts, source URLs and limitations.
  `evidence/inventory-page-*.json`, `detail-*.json`, `seu.html`, application shell,
  public JavaScript and sample approval PDF retain source captures.

Only the four municipality-specific source files are added. No shared code,
dependencies, database, deployment, publishing or repository mutation is needed.
