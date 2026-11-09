# La Almunia de Doña Godina — INE 50025, Zaragoza

Verified on 2026-11-08 using the preinstalled batch Python runtime. This adapter
extracts a partial snapshot of genuine planning instruments from the public
municipal inventory. It does not represent all public works or a granted-licence
register. Scheduling and coordinate jitter are disabled.

## Official source discovery

- https://www.laalmunia.es/ — official municipal homepage, HTTP 200, links to
  the municipal transparency page.
- https://www.laalmunia.es/portal-de-transparencia/ — HTTP 200, section
  “Información sobre ordenación del territorio y medio ambiente” links directly
  to the municipality's public electronic office below.
- https://laalmunia.sedelectronica.es/transparency/848b8283-edde-45dc-8937-311c51f3add7/
  — HTTP 200. Territory/environment inventory: “Planes urbanísticos” reports 18
  document entries; environmental information and public-information proceedings
  each report zero. The dated clock in the page header is not a record date.
- https://laalmunia.sedelectronica.es/transparency/8eb6378f-9b57-4d4a-89e9-45deb4b01174/
  — HTTP 200, actual planning inventory used by the adapter. Three top-level
  folders: PGOU (12 entries including modifications), S1 La Cuesta II (1), S3
  La Cuesta III (5 including its modification). Counts are recursive document
  entry counts, not numbers of instruments.
- https://laalmunia.sedelectronica.es/info.0 — discovery also exposed a catalogue
  of procedures such as prior works communications and responsible declarations.
  These are application procedures, not proof of granted licences, and are excluded.
  Procurement and general news are not used as project sources.

## Live scope and grouping

The complete planning tree visited 11 folder pages, with HTTP success required on
every request. Eight instrument records retain all 18 published document links:

| Instrument as labelled by the municipality | Links |
| --- | ---: |
| PLAN GENERAL DE ORDENACIÓN URBANA (ordenanzas, planos, catálogo) | 3 |
| Modificación Número 1 – El Colmenar | 2 |
| Modificación Número 2 – Catálogo | 2 |
| Modificación Número 3 – Ordenanzas Uso terciario | 2 |
| Modificación Número 4 – Polígono Industrial La Cuesta III | 3 |
| PLAN PARCIAL S1 LA CUESTA II | 1 |
| PLAN PARCIAL S3 LA CUESTA III | 1 |
| Modificación nº 2 S3 LA CUESTA III | 4 |

The PGOU modifications container is traversed, not emitted as a separate project.
The folder labelled “5.-Modificacion nº 6 TRPGOU” is empty and is explicitly
reported under `empty_folders`, not emitted as a placeholder. The ordinal “5”
is retained in the source label and is not reinterpreted as modification nº 5.
Memories, plans, announcements and agreements within one instrument remain
`documentos` on that instrument. The S3 modification and the PGOU modification
concerning La Cuesta III are separately labelled legal instruments in separate
folders; no unsupported cross-instrument merge is performed.

## Extraction and provenance

Uses requests/BeautifulSoup already declared in the repository. Public Wicket
folder actions are discovered from the current page and requested using one
anonymous HTTP session. Ordinary requests follow redirects to stable public
`/transparency/<uuid>/` URLs; no authentication, credentials or browser session is
used. Stable IDs derive from those folder URLs, not session-specific action tokens.
Every document retains its title, destination URL, containing inventory URL and
hosting provenance. External Google Drive links are published by the municipality;
this scraper does not claim the hosting service itself is a municipal domain.

All child folders are visited, including zero-count ones. Each folder's recursive
number of document entries must match its advertised count. Unexpected rows,
missing inventory markup, redirect outside the official folder routes, cycles or
pagination controls raise errors. Nothing is written until the complete extraction
succeeds. There is no hard-coded record/page limit or first-page truncation.
Update performs the same complete snapshot so undated additions are not lost to
a date watermark. Removed records require downstream snapshot handling; the
adapter does not issue database deletions or maintain incremental state.

## Dates, geography and partial coverage

Record `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` and `fase` are
null. Some document labels mention initial/definitive approval and BOP dates, but
these remain the original document titles: a bulletin publication date is not an
agreement date, and an individual historical document does not establish the
instrument's current legal status. PDF contents have not been parsed to verify
those dates or the legal effect of the documents.

The 18 links include a Google Drive folder for PGOU plans: its internal files are
not enumerated. All document destinations are retained, but their contents,
availability and geometries are outside this extraction. No spatial boundaries,
coordinates, municipal centroid or approval dates have been invented.
`publication_ready` is false. The inventory can lag other official bulletins; this
is the current publicly displayed inventory, not a claim of complete current law.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_la_almunia_de_dona_godina -v`: 9 tests passed.
  Checks grouping, nested anchor markup, external provenance, null date semantics,
  folder counts, rejection of forms/navigation/unrelated links, pagination failure,
  recursive traversal, incomplete counts, empty-source failure and manifest loading.
- Direct live `LaAlmuniaDeDonaGodinaAyuntamientoAdapter.backfill_proyectos`:
  status ok, 8 records, 18 document links, 11 folder URLs, 1 empty folder.
- `evidence/proyectos.jsonl`: real extracted instrument records.
- `evidence/validation.json`: live count, all folder source URLs, limitations,
  empty-folder report and parser test result.
- `evidence/live/*.html`: exact HTML snapshots for every page used in the live
  extraction. Additional discovery HTML is stored directly under `evidence/`.
  These captures are local evidence and are not source files to commit.
