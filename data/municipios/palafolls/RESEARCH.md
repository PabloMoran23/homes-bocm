# Palafolls — INE 08155, Barcelona

Verified live on 2026-11-07. This adapter extracts **one real planning
instrument**, grouping its published general-plan documents. Coverage is partial;
this is not an inventory of all municipal projects, amendments, public works or
granted licences. Scheduling and missing-coordinate jitter are disabled.

## Official source discovery

- Municipal urbanism service:
  https://www.palafolls.cat/serveis/urbanisme-i-territori — HTTP 200, links to
  planning and the Generalitat register.
- Current municipal planning landing page:
  https://www.palafolls.cat/serveis/urbanisme-i-territori/planejament — HTTP 200,
  explains the service and links to the RPUC search application. It is not itself
  a list of instruments and is not emitted as a project.
- Municipal transparency normative inventory, used by the adapter:
  https://seu-e.cat/ca/web/palafolls/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
  — HTTP 200. The HTML contains all 12 table rows. Seven refer to documents or
  documentation pages of the general plan. Three others are regional laws, and
  two are generic map/register links; none of these five becomes a project.
  The municipal MUC link explicitly identifies `municipi=08155`.
- https://www.palafolls.cat/serveis/urbanisme-i-territori/llicencies — HTTP 200,
  information about licence applications and prior communications, not a public
  register of granted licences. Licences remain disabled.
- The normative inventory links to the legacy municipal `informacio-oficial/pln46/`
  plan-map page. It returns HTTP 404. Its original URL and the inventory's
  descriptive narrative are preserved; it is not presented as a downloaded PDF.

## Extraction and provenance

The table supplies three 2006 plan-map PDFs, normative volumes I and II, a 2005
consolidation PDF and the legacy documentation-page link. All six PDF links were
downloaded live with HTTP 200 and verified by their PDF signature. The 2005 URL
explicitly contains `no-vigent`; this attachment is tagged `historico: true` and
does not set the main record's publication date. Its historical inclusion does
not assert that it remains effective. The listed documents belong to one plan,
not seven independent projects. Every attachment retains its title, URL,
publication date, source inventory URL and available descriptive text.

The inventory labels its date column `Data de publicació`. The 2006 attachments
and legacy page have publication date **2006-09-19**. The legacy row's narrative
explicitly gives the territorial commission's agreement as **2006-04-27** and
describes approval ex officio. The adapter records that date as `fecha_acuerdo`,
preserves the narrative, and leaves generic `fecha` and `fecha_aprob` null. It
does not infer a definitive-approval stage or copy the page's March/September
2026 update timestamps into project dates. The historical attachment has its own
publication date, **2005-12-31**.

DataTables pagination is local to the already complete HTML. The adapter reads
every tbody row, including the final volume I after the first ten rows; the live
HTML has malformed nested rows, handled using direct child cells. If server-side
loading or an active next-page link appears, extraction raises an error rather
than silently returning a partial page. Missing inventory/volume, invalid dates,
conflicting duplicates and unexpected document hosts also fail explicitly.

Backfill and update refresh this entire scoped snapshot, atomically replacing
the output only after successful parsing. They do not filter by a publication
cutoff. No additional RPUC dossier history or geometry API has been implemented.
The map PDFs are documents, not extracted vector geometry: `lat`, `lon` and
`geometry` remain null and `publication_ready` is false. No municipal centroid,
random coordinates, fabricated identifier or synthetic approval date is used.
The stable local record ID identifies the grouped general plan and is not
represented as an official expediente number.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_palafolls -v`: **8 tests passed**, covering grouping,
  publication/agreement semantics, historical attachments, all rows beyond the
  browser's first page, rejection of forms/navigation, pagination changes,
  malformed dates and provenance, deduplication, snapshot writing and manifest
  loading through the existing registry.
- Direct live `PalafollsAyuntamientoAdapter.backfill_proyectos`: **1 record**,
  seven retained links, six confirmed PDFs; one known broken legacy page.
- `evidence/proyectos.jsonl`: actual live adapter output.
- `evidence/validation.json`: live count, source URLs, limitations, test results,
  document HTTP statuses, capture paths, byte counts and SHA-256 hashes.
- `evidence/normativa-live.html`: exact source body used for live extraction;
  discovery HTML and six PDF captures are also under `evidence/`.

Evidence remains local and uncommitted. No shared adapter/schema files,
dependencies, credentials, databases or deployment tools were changed or used.
