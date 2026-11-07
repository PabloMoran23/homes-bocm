# Laviana — Asturias — INE 33032

Research and live verification: 2026-11-07. This adapter covers the public
Principado de Asturias RPGUR inventory for **municipal Laviana instruments marked
Vigente**. It is a planning/urban-management inventory, not a licence register or
a complete list of physical public works. Scheduling and coordinate jitter are
disabled. No coordinates or geometry are inferred; `publication_ready` is false.

## Sources discovered

- https://www.ayto-laviana.es/normativa-urbanistica — municipal explanation of the
  Registro de Planeamiento y Gestión Urbanística and links to regional sources.
  It explicitly warns that the registry offers general planning and only part
  of development planning. Its old `www28.asturias.es` link did not resolve.
- https://www.ayto-laviana.es/convenios-urbanisticos — municipal historical-query
  page links to the working `www54.asturias.es/rpgur` public application. No login
  is needed. Session identifiers in old links are discarded, not reused.
- https://www54.asturias.es/rpgur/action/publico/busquedaConsulta?method=listPublico&primeraVez=false&ambito=MUN&idConcejo=32&estado=V
  — the actual inventory, HTTP 200. The public form identifies LAVIANA as concejo
  32. Its 26 results occupy pages 1 (1–15) and 2 (16–26). The implementation follows
  `Siguiente`, honors the HTML JSP `<base>` for relative links, checks consecutive
  ranges, unique instrument identities and total count, and fails rather than
  write a truncated or inconsistent snapshot. A 100-page safety limit raises an
  error; it never silently accepts the prefix.
- https://www54.asturias.es/rpgur/action/publico/gestionConsulta?method=retrieve&idInstrumento=2681
  — example actual planning detail: Plan General Ordenación de Laviana, expediente
  C-0648/09. It identifies the municipal scope and current status, agreement
  2010-11-26, definitive-approval BOPA publication 2011-01-27, and separate
  texto-refundido publication 2012-04-19. Each detail is checked against its
  inventory title, municipality, state, expediente and hidden instrument ID.
- https://www54.asturias.es/rpgur/action/publico/gestionConsulta?method=retrieve&idInstrumento=2680
  — Catálogo Urbanístico: a distinct instrument sharing C-0648/09 with the Plan
  General. These must not be collapsed on expediente alone. Notes preserve the
  subsequent Coruxera modification rather than claim the base approval is its date.
- https://www54.asturias.es/rpgur/action/publico/gestionConsulta?method=docs&idInstrumento=2681
  — grouped technical documents and plans. Download links have stable
  `idDocumento` values. Document titles and source listing URLs are retained on
  the parent instrument. Document files are not emitted as separate projects.
  Some instruments explicitly say `No existen Documentos`; unavailable/blocked
  trees are separately flagged. Source document contents are not exhaustively
  parsed or treated as project geometry. The source's document-page `Volver`
  links can point to unrelated IDs; those navigation links are not provenance.
- https://www.asturias.es/temas/vivienda-territorio/gestion-urbanistica-y-registro-planeamiento/visor-gestion-urbanistica
  — current regional description and public register/viewer links. Each record
  retains its instrument-specific `sigvisor.asturias.es` viewer URL; no map
  centroid, approximate point, or raster plan is substituted for geometry.

## Municipal PDF and date discrepancy

https://www.ayto-laviana.es/normativa-urbanistica1 names the Plan General and
Catálogo and links to
https://sede.asturias.es/bopa/disposiciones/repositorio/LEGISLACION38/66/7/001U004TK50001.pdf
(HTTP 200 after redirect to `miprincipado.asturias.es`). The captured 445-page PDF
has a first-page header saying `núm. X de 24-iv-2012`, whereas the municipal page
and RPGUR specify 19 April 2012. It contains the 14 December 2011 approval of the
texto refundido and refers to the earlier 26 November 2010 approval. This is why
the scraper uses explicitly labelled registry dates, retains all labelled
milestones and their provenance, and does not guess dates from PDF headers,
URLs, crawl time or unstructured notes. The legacy PDF is supporting research,
not an additional instrument or the runtime inventory.

## Scope and semantics

One row per actual RPGUR instrument ID: Plan General, Catálogo, modifications,
Planes Especiales, Estudios de Detalle and urban-management projects. One
Convenio Urbanístico is excluded explicitly in the extraction report. No licence
application, procurement announcement, navigation link or unrelated news becomes
a record. Missing expediente values remain null; real registry IDs are never
presented as municipal expediente numbers.

`estado` retains the register's `Vigente`; this is not a claim of construction or
licence grant. `tipo` and dates do not synthesize a project phase. `fecha` is null;
`fecha_acuerdo`/`fecha_aprob` refer only to the labelled definitive approval,
`fecha_publicacion` to its labelled BOPA publication, and the texto-refundido
publication has its own field. All dated milestones remain under `hitos`.

Update performs the same full current-inventory refresh as backfill. Mandatory
inventory/detail failures leave an existing output untouched. Optional document
listing failures retain the verified instrument and a diagnostic flag and URL.
Historical, in-progress, supramunicipal and unregistered instruments, public
works outside RPGUR, attachment contents and project geometries remain outside
coverage. No claim of legal validity beyond the registry's displayed status is
made. `licencias.enabled=false` because no granted-licence inventory was verified.

## Reproducible validation

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Only existing `requests` and `beautifulsoup4` dependencies are used by the adapter.

- Parser tests: `python -m unittest municipio.test_laviana -v` (using that runtime).
  Inline fixtures exercise pagination, count and municipality guards, distinct
  dates, missing dates, identity checks, document grouping, explicit empty file
  inventories, convenio exclusion, complete refresh and atomic failure.
- Live extraction: `load_manifest('laviana')`, `load_portal_adapter(manifest)`,
  `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`. The optional
  config `capture_dir='evidence/live'` saves actual response bytes for audit.
- Result: **12 tests passed; 25 real records from all 26 results over two pages**,
  with one convenio excluded and 108 document links grouped on the instruments.
  Eighteen file trees explicitly report no documents. The file tree for instrument
  7044 was unavailable; the verified instrument and its document-inventory URL
  remain, with an explicit limitation. Shared entity-policy annotation reports
  25 total and two records without sufficient identity for automatic activity
  eligibility (missing expediente); no reference is fabricated to override it.
- Local, uncommitted evidence: `evidence/proyectos.jsonl`,
  `evidence/validation.json`, live HTML captures and research HTML/PDF/text.
  Validation records actual live totals, source URLs and limitations.

No shared modules, dependencies, credentials, database, deployment or publication
operations are part of this implementation.
