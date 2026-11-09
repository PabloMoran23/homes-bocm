# Ugena — Toledo — INE 45176

Verified live 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Exactly one adapter, with deliberately partial planning inventory coverage.
Scheduling and licences are disabled; missing geometry is never jittered.

## Official source discovery

The current municipal homepage https://www.ugena.es/ links directly to
https://ugena.sedelectronica.es/transparency. The municipal WordPress pages API
(`https://www.ugena.es/wp-json/wp/v2/pages?per_page=100`) returned one page of
41 pages, with no standalone planning inventory. The electronic headquarters
is the usable structured official source, accessible anonymously.

Official transparency hierarchy (all HTTP 200 during research):

- Territorial/urban information:
  https://ugena.sedelectronica.es/transparency/e2721061-d303-4ea7-86e2-239644d77f11/
- Urbanismo:
  https://ugena.sedelectronica.es/transparency/5d28aad7-b842-48da-b40a-9311ce63eb36/
- Normativa urbanística:
  https://ugena.sedelectronica.es/transparency/0e6e7101-c443-48f5-b863-0beca891ca33/
- Normativa en vigor (adapter entry point):
  https://ugena.sedelectronica.es/transparency/a9e4a3f2-d04c-4680-94ba-7d79c4f796e9/
- Normas Subsidiarias Municipales de Ugena:
  https://ugena.sedelectronica.es/transparency/c94f9e4f-a7cb-4570-85d5-ba4668e6fed0/
- NNSS / Planos:
  https://ugena.sedelectronica.es/transparency/2bee1d16-b6f8-44a5-9783-d743aff692d9/
- Plan parcial SECTOR 13 EL LLANO: direct document listed under normativa en vigor:
  https://ugena.sedelectronica.es/preview-document/b2e7f511-87b1-4930-a72e-e5f1ed5591e0

Other discovered inventories, explicitly outside extraction scope:

- Modificaciones puntuales (six documents, including multiple documents for
  the same modification):
  https://ugena.sedelectronica.es/transparency/c833426a-7ded-4538-bf75-164fbc450864/
- Normativa en tramitación (POM folder, 1,367 documents):
  https://ugena.sedelectronica.es/transparency/69a4bc28-b077-4a16-ad27-0d94dde542ef/
- Ejecución del planeamiento (mixed planning and photovoltaic notices):
  https://ugena.sedelectronica.es/transparency/f7ea059d-0c27-4270-a48d-06e22aee1a99/
- Licencias y autorizaciones (historical lists for 2018–2020):
  https://ugena.sedelectronica.es/transparency/97a54f20-7a90-4ec2-bc18-c385d52b5d28/
  These do exist; disabled licences must not be interpreted as their absence.
- Obras públicas e infraestructuras is shown with zero documents in the
  urbanismo inventory. This does not establish the absence of municipal works.

## Record semantics and provenance

Two records are extracted: the NNSS, grouping all 29 source documents, and the
Sector 13 partial plan with one document. The six NNSS top-level documents and
23 planos are one instrument, not 29 projects. Annexes retain their exact source
titles, including archaeological sheets named after neighboring map areas;
they are not interpreted as separate Ugena projects or locations.

Each record retains its inventory URL, document titles, official preview links
and document inventory provenance. The preview links are document references,
not claims that PDF bodies, approval clauses or geometries have been parsed.
The official classification `NORMATIVA EN VIGOR` is recorded as `estado_fuente`;
it is not transformed into an approval phase or agreement date. Generic,
publication, agreement and approval dates are null. No scrape timestamp,
filename year or website clock is used as a legal date. Coordinates and geometry
are null; `publication_ready` is false.

Stable record identity hashes the actual instrument folder/document URL.
Backfill and update refresh the same complete scoped snapshot; no licence
forms, procurement announcements, navigation labels or unrelated news become
records. This is neither full municipal history nor full current planning
coverage: modifications, pending POM, execution notices and works are excluded.

## Pagination and failure behavior

The anonymous GestIona/Wicket session exposes folder navigation actions and
`Mostrar más` actions. The adapter reads their server-provided URLs using one
requests session; no scripts are executed. Pagination responses are XML with
HTML inside component CDATA; only those components are parsed. The same action
URL can advance several pages, so repeated *page contents*, not repeated URLs,
are rejected. All three planos batches (10 + 10 + 3) are consumed. Child counts
(23) and total NNSS count (29) must match the current parent declarations.
Duplicates, missing named instruments, malformed XML/navigation, unexpected
hosts, root pagination changes, repeated pages, excessive depth or size bounds
raise errors before output is written. Bounds never return a silently truncated
snapshot. Document-count checks intentionally require review if the inventory
changes structure.

## Validation and evidence

- `python -m unittest municipio.test_ugena -v`: seven tests passed. Coverage:
  inventory selection, XML components, repeated-action pagination, stalled pages,
  incomplete folder counts, grouping/identity/date semantics, source host checks
  and disabled licences. Fixtures are synthetic parser inputs, not live records.
- Live extraction used `load_manifest('ugena')` and `load_portal_adapter`, then
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
- Result: **2 actual instruments, 30 document references**, NNSS document count
  fully matched, no coordinates or dates inferred.
- Local `evidence/proyectos.jsonl`, `evidence/validation.json`, discovery HTML
  captures and `evidence/live/source-*.html` contain the extraction evidence.
  Live captures include the XML pagination components. Evidence is local only.

No dependencies, shared code, credentials, databases, deployment services or
Git configuration were changed or used.
