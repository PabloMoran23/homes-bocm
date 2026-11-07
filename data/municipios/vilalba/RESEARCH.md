# Vilalba — Lugo — INE 27065

Verified live 2026-11-07. One real planning instrument, with 45 linked components,
extracted through `VilalbaAyuntamientoAdapter`. Scope is deliberately partial:
**the base Normas Subsidiarias de Planeamento only**. This does not represent a
consolidated version, all municipal planning, an inventory of works, or granted
licences. Scheduling and missing-coordinate jitter are disabled.

## Official source discovery

- [Municipal Urbanismo](https://www.vilalba.gal/concello/areas-do-goberno/urbanismo-mobilidade-infraestructuras-rurais-e-desenvolvemento-industrial/urbanismo/)
  responds HTTP 200. Its PXOM link is only `#`, not an extractable instrument.
  Service descriptions and licence applications are not records.
- [Municipal Marco Urbanístico](https://www.vilalba.gal/concello/areas-do-goberno/urbanismo-mobilidade-infraestructuras-rurais-e-desenvolvemento-industrial/marco-urbanistico/)
  responds HTTP 200 and links SIOTUGA at the legacy address
  `http://www.planeamentourbanistico.xunta.es/siotuga/inventario.php`.
  The current official HTTPS service is hosted by the Xunta.
- [SIOTUGA Urbanismo](https://siotuga.xunta.gal/siotuga/urb) identifies the exact
  row `27065 / Vilalba / Normas subsidiarias de planeamento / 1984-03-13`.
  Its category is general planning not adapted to the LOUG. This is evidence
  of the source inventory classification, not a new finding of legal validity.
- [Municipal inventory](https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=27065)
  exposes an anonymous form. The HTML alone contains no dossiers; the adapter
  uses the same public JSON requests as its JavaScript, with a fresh public form
  token and session, without credentials.
- The page's `assets/inventario/controls.min.js?2.5.0` documents
  `POST assets/inventario/query_document.php` with `id=27065`, `idclase=14`
  and the anonymous form token. It returns the entire general-planning array,
  including nine entries during discovery. Class 13 returned ten development
  entries, class 16 null and class 18 one rural delimitation during discovery.
  These other instruments are outside the adapter's declared coverage.
- The adapter selects exactly one base NSP by source figure and full title,
  discovers its actual document identifier (28576 in this run), and calls
  `POST assets/inventario/getIOTPU.php` with `iddoc`, `idp=0`, `lang=gl_ES` and
  the form token. It verifies title, figure, identifier, municipality and dates
  against the listing. No inventory IDs or component filenames are fabricated.

## Extracted instrument and provenance

`NORMAS SUBSIDIARIAS DE PLANEAMENTO DE VILALBA` is one record; its memories,
approval report, 41 plans and urban regulations are 45 components retained in
`documentos`, each with its section, label, source component ID and actual URL.
Links are built exactly as the official UI does from `filesroot`, `folder` and
`pathesperado`. Their source directory is
`https://siotuga.xunta.gal/siotuga/documentos/urbanismo/VILALBA/documents/`.
The approval report `28576me003.pdf` was independently fetched: HTTP 200,
`application/pdf`, 2,590,413 bytes, PDF signature confirmed. Not all 45 PDFs
were downloaded or independently inspected. Geometry is not inferred from plans.

The source's `fechaaddef` is 1984-03-13 and maps to `fecha_aprob`. `fechabop`
and `fechanormativabop` are both 1984-04-30 and are retained as separately named
BOP publication fields. `fechadog` is null. Generic `fecha`, `fecha_acuerdo` and
`fecha_publicacion` remain null, avoiding a choice between publication channels
or an invented agreement date. Dates are inventory metadata, not independent
transcriptions of the PDF contents. Raw date fields and legal incidents are
retained. Stable record identity uses the source dossier ID.

The endpoint sends a complete JSON array: DataTables sorts and paginates that
array in the browser, with no server page/limit parameters in the official
request. The adapter reads the complete response before selecting the base NSP;
it does not take the first page or silently cap rows. A changed response shape,
missing or duplicate matching instruments, mismatched details, empty component
lists, unexpected document hosts, HTTP errors and oversized responses fail the
snapshot. Updates refresh this same complete, narrow snapshot.

## Validation and limitations

Runtime used:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `PYTHONDONTWRITEBYTECODE=1 .../venv/bin/python -m unittest municipio.test_vilalba -v`:
  **7 tests passed**. Tests cover distinct date meanings, unknown dates, exact
  instrument selection, ambiguous/missing records, pagination wrapper rejection,
  document grouping, wrong-municipality and detail mismatches, component path
  escape, and the disabled manifest/licence settings.
- Live extraction via `load_manifest('vilalba')`, `load_portal_adapter(manifest)`
  and `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 record,
  45 document links**. The existing entity policy reports `unknown` for this
  planning category, status `ok`; no shared policy was changed.
- Local `evidence/validation.json` records live count, URLs, limitations,
  test outcome, PDF probe and pagination behavior. Compressed source HTML,
  JSON and municipal discovery captures are under `evidence/`. Compression
  was used because the workspace filesystem reported no free space; extraction
  and evidence writes nevertheless completed after moving temporary captures.

No verified public granted-licence register was established. No amendment,
development instrument, rural delimitation, territorial project, procurement
announcement or unrelated news item is emitted. Other inventories may contain
useful records, but are not claimed as covered. No coordinates, municipal
centroid or geometry are substituted: `lat`, `lon`, `geometry` are null and
`publication_ready=false`. Presence of old approved documents in the current
inventory does not by itself establish their unmodified present legal force.
Evidence is local and is not intended for commit.
