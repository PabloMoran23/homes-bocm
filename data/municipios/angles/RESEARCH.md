# Anglès — INE 17008, Girona

Verified live on 2026-11-09 using the preinstalled batch virtual environment.
One municipal adapter covers the physical works documented in the public
Som.Anglès project inventory. This is a deliberately partial historical snapshot,
not a comprehensive inventory of present-day works. Scheduling, missing-coordinate
jitter and licence extraction are disabled. All records have publication_ready=false.

## Official source discovery

- https://www.ajangles.cat/ — current official municipal website, HTTP 200;
  links to Urbanisme i Territori and the municipal electronic seat.
- https://www.ajangles.cat/urbanisme-i-territori/ — HTTP 200; description of the
  municipal service, without extractable project dossiers. Not emitted as a project.
- https://seu-e.cat/ca/web/angles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200 (the www/web URL redirects here). Public planning page links to
  RPUC dossier 247776 and two planning PDF sheets, 1.1_REGIM_DEL_SOL and
  1.2a_SISTEMA_MOBILITAT_MUNICIPAL. This page's update timestamp is not an
  approval date. These sheets were not turned into separate projects; planning
  extraction is outside this adapter's reviewed coverage.
- https://som.angles.cat/projectes/llistat — HTTP 200; structured municipal
  project inventory. The site identifies itself as the Ajuntament d'Anglès
  government-open portal and links the municipal website in its footer. It is
  a legacy Drupal portal still publicly accessible; no claim of recent upkeep.
  Six project entries were present, with no pager on the live page. Four are
  physical works and two are social/community programmes.
- https://www.ajangles.cat/portal-de-transparencia/ — HTTP 200, inspected for
  current transparency navigation; not an additional project source.

The CIDO planning index was also found during official-source discovery:
https://cido.diba.cat/normativa_local/6987526/planejament-urbanistic-ajuntament-dangles.
It points to a broader planning history, but is not scraped here. No claim is made
that this adapter covers that history, the electronic noticeboard, all municipal
news, procurement or granted building licences.

## Live records

| Drupal node | Physical project | Page publication |
| --- | --- | --- |
| 1490 | Rehabilitació dels habitatges del carrer Fàbriques (ARRU) | 2019-06-30 |
| 1489 | Reforma dels lavabos del CEIP Pompeu Fabra | 2019-06-28 |
| 1305 | Connexió de les aigües residuals del c/Fàbriques al sistema de sanejament | 2017-03-12 |
| 162 | Adequació dels locals A i B de la Nau Burés nº3 | 2016-12-27 |

Exact inventory and detail URLs are listed in evidence/validation.json and each
record's url/source_inventory fields. Detail pages supply substantial works
narratives, not just titles or procurement links. The ARRU intervention describes
rehabilitation of 72 occupied dwellings in partnership with public administrations
and owners; this is a publicly supported physical intervention, not a building
licence. School toilets, sewer connection and Burés premises adaptations are
likewise documented physical works.

Node 120, Projecte d´Acció Social i Inserció Laboral, is an employment/social
programme; node 122, Polítiques d´habitatge…, concerns organisation and mediation
of residents' communities before possible repairs. Both were inspected and
excluded rather than counted as works. Their exact titles/URLs are in validation.
Unknown new title categories cause a review error instead of silently disappearing.

## Semantics, provenance and limits

- Stable IDs use the actual Drupal node ID. Each detail identity and title must
  match its inventory entry. Documents remain grouped under their project;
  duplicate document URLs are collapsed, never emitted as separate works.
- Publication comes only from the explicit `Publicat` field. Start/end dates
  come from their labelled fields. Generic fecha, fecha_acuerdo, fecha_aprob and
  fase remain null: the adapter does not derive approval from publication,
  procurement links or reported completion.
- Node 162 reports start 20/11/2017 and end 15/12/2016. Both source values are
  retained, with a record-level quality warning; no year has been corrected.
- The ARRU page links two agreements, including an addendum whose label mentions
  a 2017 bilateral commission. This is document provenance, not a verified
  agreement date for the entire project. Both URLs and labels are retained in
  documentos. Procurement and media links remain enlaces_relacionados; their
  presence alone does not establish a licence or a project.
- Linked documents are retained as published, including legacy HTTP links. Their
  availability and contents have not been verified (`content_verified=false`).
  No dates are extracted from unseen PDFs. Some works have no linked technical
  documents; their municipal detail narratives remain the primary evidence.
- Detail pages include Drupal deprecation warnings outside article content.
  The parser selects the project article, excluding warnings, menus, votes,
  user login/comment prompts and the municipal footer from descriptions.
- No verified coordinates or project geometries appear in these fields. lat,
  lon and geometry stay null; municipal-address coordinates are not substituted.

## Extraction and validation

Backfill and update refresh a complete inventory snapshot. All pager URLs are
queued, deduplicated and traversed, including numbered pages; a changed/missing
inventory or failed detail aborts before replacing output. The safety limit of
100 pages raises an error rather than returning a truncated success. Requests
have 30-second timeouts and a 5 MB response bound. The parser requires physical
works prose and rejects mismatched detail identity. Licence methods produce an
empty disabled output; no forms are converted to granted licences.

Commands executed with
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`:

- `-m unittest municipio.test_angles -v`: 7 tests passed. Covers distinct date
  semantics, missing/anomalous dates, document grouping/provenance, excluded
  programmes, unknown categories, navigation/non-work rejection, detail identity,
  pagination with cycle deduplication, failed-page output preservation and manifest
  adapter loading.
- Live manifest/registry-loaded adapter `backfill_proyectos`: 4 real records,
  6 inventory entries, 2 exclusions, 1 inventory page and 4 detail fetches.
- Assertions checked unique IDs, INE 17008, null geometry/approval dates and the
  three required disabled manifest settings. Shared entity policy annotation
  reports status ok, unknown categories for all four records; it supplies no
  stronger semantic verification or publication readiness.

Local, uncommitted evidence: evidence/proyectos.jsonl, evidence/validation.json,
source discovery HTML captures, and evidence/captures/*.html from the adapter's
live requests. Capture filenames are SHA-256 URL prefixes. No shared source or
dependency changes, publishing, deployment or git mutations are required.
