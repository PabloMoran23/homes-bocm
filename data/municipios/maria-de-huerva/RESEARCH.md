# María de Huerva — Zaragoza — INE 50163

Verified 2026-11-09 using the preinstalled batch virtualenv. This adapter extracts
one actual planning instrument from the municipal document inventory. Coverage is
partial; `publication_ready` is false. It does not claim comprehensive current
planning, all amendments, physical works or granted licences.

## Official source discovery

- https://mariadehuerva.org/ayuntamiento/urbanismo/ — municipal urbanism index;
  links to PGOU and technical services. The isolated text “Pendiente de aprobación”
  does not identify a decision or date and is not used to infer the PGOU's phase.
- https://mariadehuerva.org/ayuntamiento/urbanismo/pgou/ — HTTP 200 on the live
  extraction. The named Plan General de Ordenación Urbana inventory exposes
  37 PDF links: two core documents (fichas and normas), 23 information,
  infrastructure and ordering plans, and 12 protection-catalogue parts.
  All are grouped into one PGOU record with the original labels, absolute URLs,
  section and inventory provenance. Infrastructure drawings are components of
  this plan, not independently evidenced construction projects.
- https://mariadehuerva.org/wp-content/uploads/2022/04/NORMAS-URBANISTICAS.pdf —
  HTTP 200, verified PDF signature, 1,304,257 bytes; downloaded to local evidence.
  Remaining documents are retained as inventory links, not individually downloaded
  or interpreted. The upload directory's year/month is not a publication or
  agreement date.
- https://mariadehuerva.org/ayuntamiento/urbanismo/servicios-tecnicos/ — describes
  municipal services, including licence management; not a granted-licence register.
- https://mariadehuerva.sedelectronica.es/info.0 — official procedures catalogue;
  application/declaration forms are not licence grants and are not extracted.
- The municipal navigation links its transparency service at
  http://mariadehuerva.cumpletransparencia.es/mariadehuerva/Home.
  The public inventory was inspected at
  https://www.cumpletransparencia.es/mariadehuerva/Ordenacion/informacion-obras-publicas-proyectos-pliegos-y-criterios
  (HTTP 200, captured locally). It lists 2023 services, concessions and procurement
  entries, including police-station construction, football changing-room extension
  and street repairs; police-station entries repeat. It links previous exercises.
  These entries and historical pages are outside this adapter's PGOU scope:
  underlying project dossiers were not verified and procurement entries alone
  are not promoted to project records. Its February 2024 update timestamp is not
  treated as an approval date. No exhaustive works-history claim is made.
- Municipal transparency also points users to the regional planning archive:
  https://www.cumpletransparencia.es/mariadehuerva/Ordenacion/planes-de-ordenacion-urbana-y-usos-y-destinos-del-suelo
  describes an interactive search through https://idearagon.aragon.es/SIUa.
  That archive is not implemented by this adapter; its amendments and legal status
  are not asserted from the municipal PDF inventory.

## Extraction decisions and limits

The adapter implements the existing AyuntamientoAdapter contract and is resolved
through the manifest's module/class specification without shared changes. Both
backfill and update fetch a complete snapshot of the single PGOU inventory page.
There is no pagination on the inspected page, no record cap and no slicing of
links. Pagination controls cause an error if introduced. A missing content region,
wrong page/redirect, missing core documents or catalogue, or a foreign document
host also causes an error instead of emitting a placeholder. Repeated PDF URLs
are deduplicated. Navigation PDFs are excluded by the content boundary.

Dates of publication, agreement and approval remain separately null because this
inventory does not establish them. No crawl date, file path, general-page text or
last-modified header is used as a legal date. No approval phase or current legal
validity is inferred. The catalogue is grouped with the PGOU because it is listed
alongside that plan on the same instrument page; no separate proceeding is claimed.
No coordinates or geometry are invented from the municipal location or drawings.
Licences, scheduling and missing-coordinate jitter are disabled in the manifest.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_maria_de_huerva -v`: four tests passed. They check
  grouping/deduplication, navigation exclusion, absent date semantics, missing
  source content, pagination and foreign provenance rejection, manifest resolution,
  update wiring and disabled licences.
- Real `load_portal_adapter(load_manifest('maria-de-huerva')).backfill_proyectos`
  execution: one record, 37 document links. Shared entity annotation ran normally;
  it classified this planning instrument as unknown (not a housing-development
  claim). No shared policy changes were made.
- Local `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/pgou.html`,
  `evidence/normas-urbanisticas.pdf` and `evidence/transparencia-obras.html` preserve
  extraction results, source captures, limitations and the PDF checksum.
  Evidence is not part of the source changes.
