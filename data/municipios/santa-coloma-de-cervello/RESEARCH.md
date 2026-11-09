# Santa Coloma de Cervelló — INE 08244, Barcelona

Verified live 2026-11-08 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The implemented scraper covers **23 real instruments / public works**, with
**172 document links**, from three official municipal transparency inventories.
This is partial municipal coverage, not a granted-licence register. Scheduling,
licences and missing-coordinate jitter are disabled. No coordinates or geometry
are inferred; `publication_ready` is false.

## Official source discovery

- Municipal urbanism service:
  https://www.santacolomadecervello.cat/10-serveis/serveis/urbanisme.html
  describes planning, management and works responsibilities; its service and
  licence-application descriptions are not emitted as records.
- Official transparency urbanism navigation (captured, HTTP 200):
  https://seu-e.cat/ca/web/santacolomadecervello/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
  explicitly links the following inventories.
- Planning under processing (HTTP 200, six instrument sections):
  https://seu-e.cat/ca/web/santacolomadecervello/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic-en-tramitacio-217
  Includes Torre Salbana partial plan; Colònia Güell industrial precinct PGM
  advance; Ajuntament Vell special plan; Casal de Cesalpina PGM amendment;
  Font Vella PAU-1 reparcellation; Llobregat landscape/access specific-action
  project, phase II. Inventory update label: 01/06/2026.
- Reparcellation inventory (HTTP 200, five sections):
  https://seu-e.cat/ca/web/santacolomadecervello/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-de-reparcel-lacions-218
  Includes Torre Salbana urbanisation (separate from its partial plan), Font
  Vella PAU-2, Font Vella PAU-1 consolidated project and correction, Colònia
  Güell industrial precinct reparcellation amendment, and municipal land
  grouping/segregation at Països Catalans / Joan XXIII / Santa Coloma / La Pau.
- Public works inventory (HTTP 200, thirteen sections):
  https://seu-e.cat/ca/web/santacolomadecervello/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-d-obres-219
  Includes pavilion photovoltaic installation; library extension/HVAC;
  accessibility to the town hall; Les Carboneres rehabilitation; Vinyes slope;
  Can Soler stream naturalisation; Assecadors roof consolidation; Can Via and
  Cesalpina slope improvements; Can Lluch overflow; Güell football-ground
  canopy; cemetery car park reurbanisation; resurfacing of municipal roads.
  Inventory update label: 22/10/2026. These are technical projects with documents,
  not procurement announcements or unrelated news. No assertion of execution
  or completion follows from approval or publication.
- General planning page (captured, HTTP 200):
  https://seu-e.cat/ca/web/santacolomadecervello/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  has explanatory content / register navigation rather than a usable instrument
  inventory in the downloaded HTML; it emits no records. No exhaustive RPUC,
  historical bulletin or licence-grant crawl is claimed.

## Parsing, provenance and completeness

Each complete rich-text inventory is downloaded, with timeout and a 4 MB response
limit; an oversized response fails. No row count or first-page truncation is used.
The reviewed pages have no pagination links. Any detected next link or linked
pagination control raises an error requiring crawler review. Unknown headings,
missing document groups and links outside parsed paragraphs also fail rather
than quietly producing partial output. Failed extraction leaves the prior JSONL
unchanged. Update refreshes all three snapshots; state is not an incremental
cursor. Site redesigns require parser review.

Paragraph heading boundaries group the memory, plans, annexes, notices and
successive approval documents into an instrument. Font Vella PAU-1 appears on
two pages: its explicit matching subject and shared official document folder
`18483973` justify merging those sections, retaining both source titles, URLs
and all documents. The 24 source sections therefore yield 23 instruments.
Other IDs hash the published title; PAU-1 uses a stable instrument key. Title
changes on other instruments may change their IDs. Document folders are not
invented expediente numbers. The scraper does not infer municipal file references.

Each document retains its absolute URL, link title, paragraph context and source
inventory URL. Empty source labels are retained with context. External BOPB and
municipal document-validation links are retained, not fetched or used to derive
facts. PDFs are not downloaded or parsed by this adapter; approval details inside
PDFs may therefore be absent. Correction and amended-project links stay with
the parent instrument. Inventory inclusion does not prove current legal validity.

Full explicit day/month/year dates and Catalan written dates become contextual
`eventos`; BOPB labels are publication events, explicit agreement/body/decree
labels are agreement events, and other dated labels remain document-date events.
For example, Can Lluch's BOPB 07/08/2026 is publication, while Llobregat phase
II's certificate 8 de maig 2026 is an agreement. Month-only labels, dates with
source typos (e.g. `desmebre`) and absent dates are not repaired or invented.
Page-update timestamps and dates embedded only in filenames are never project
approval/publication dates. Since an instrument may contain multiple successive
acts, top-level date and phase fields remain null; source wording and events
retain those distinctions without asserting one latest stage.

## Validation and limitations

Six offline parser tests pass: multiline/nested document grouping and mixed-case
heading suffixes; date semantics; cross-inventory consolidation and stable PAU-1
identity; rejection of forms, login, pagination, missing documents and orphan
links; update/failure behavior; manifest/registry integration.

Command:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_santa_coloma_de_cervello -v`

Live extraction was run through `load_portal_adapter(load_manifest(...))` and
`backfill_proyectos`, not a synthetic fixture. Local `evidence/proyectos.jsonl`
and `evidence/validation.json` contain records, counts, source URLs, limitations,
test results and capture hashes; complete source HTML is also in `evidence/`.

The shared entity-policy classifier reports 23 `pendiente` entities and
`adapter_incident / unknown_entity_spike`: its referenced-record rules require
an expediente number, which these inventory pages do not supply. We preserve
that result in evidence rather than inventing references or altering shared
policy. The adapter is a reviewable extraction of documented instruments;
it is **not publication-ready** and does not claim downstream ingestion approval.
The classification limitation is additional to the absence of verified geometry,
partial historical coverage and unparsed PDF contents. No licences are emitted.
