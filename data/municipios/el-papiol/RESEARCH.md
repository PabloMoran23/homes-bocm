# El Papiol — INE 08158, Barcelona

Verified on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One municipal adapter; partial coverage of publicly listed planning and physical
works dossiers. Scheduling, granted-licence extraction and coordinate jitter are
disabled. No verified geometry is available; `publication_ready` is false.

## Official source discovery

Municipal urban-planning index:
https://www.elpapiol.cat/ajuntament/informacio-publica-oficial/planejament-urbanistic-gestio-urbanistica-i-activitats/

Live HTTP 200; links to the two inventories below, the activities consultation
page, RPUC and AMB cartography. The generic RPUC entry and cartographic links are
not individual instruments and are not emitted as projects. The index also
summarizes the fire-prevention project; it is not emitted again.

Planning inventory (HTTP 200):
https://www.elpapiol.cat/ajuntament/informacio-publica-oficial/planejament-urbanistic-gestio-urbanistica-i-activitats/planejament-en-exposicio-publica

- Pla General Metropolità PA06 DEL PAPIOL: one municipal listing and an official
  e-TAULER link, `idEns=815800000&idEdicte=605673`. The linked URL returned HTTP
  200 but only a JavaScript application shell. Title and exhibition classification
  come from the municipal inventory, not unseen edict content. No approval date
  or more specific instrument description is inferred.
- Modificació puntual del PGM del Camí del Puigmadrona: six linked PDFs,
  including memory, drawings, environmental documentation, preliminary
  urbanization project, council proposal and council agreement. These constitute
  one instrument, not six projects. Initial approval is stated in its heading.

Works inventory (HTTP 200):
https://www.elpapiol.cat/ajuntament/informacio-publica-oficial/planejament-urbanistic-gestio-urbanistica-i-activitats/projectes-en-exposicio-publica

- Photovoltaic pergolas for collective self-consumption at the commuter parking
  area: one technical-memory PDF.
- Ordinary works project for the Sala Polivalent: 23 linked documents, including
  project transmission, budget, technical specifications, drawings, memory
  annexes, proposal and agreement. One project with all documents retained.
- Initial approval of fire-prevention clearing/thinning projects for the exterior
  protection strip (FP) and internal municipal plots (PM): 43 documents retained
  as one jointly published dossier, following the site's grouping. Administrative
  models, draft orders, servitude documents and decrees remain attachments; none
  becomes a granted licence or independent physical project.

Activities exhibition (HTTP 200):
https://www.elpapiol.cat/ajuntament/informacio-publica-oficial/planejament-urbanistic-gestio-urbanistica-i-activitats/llicencies-dactivitats-en-exposicio-publica

The page says there are currently no activities licences on public exhibition.
This is neither a granted-licence register nor evidence that no licences exist.
No licence records are emitted. Procurement announcements, application forms and
unrelated news are outside this adapter's scope.

## Extraction contract and limits

Both inventories expose all dossier sections in a single HTML response without
pagination on the verification date. The adapter reads every `.subtitle` section
in the article, collects all links until the next section and deduplicates exact
attachment URLs. Unexpected headings, missing documents, unknown link hosts,
changed content, redirects, duplicate dossier identities, detected pagination and
oversized responses raise errors before the output snapshot is replaced. New
pagination must be implemented before accepting output; no page limit silently
truncates results. Backfill and update refresh both complete inventories.

Stable dossier identity uses the actual municipal document directory, or the full
PA06 edict URL. Directory names and filename dates are not interpreted as official
expediente numbers or approval dates. Every document retains its title, URL and
source inventory URL. Titles are taken verbatim from the inventories. Generic
exhibition phase is sourced from the section; initial approval is used only where
the dossier heading explicitly states it.

The planning page update is 2026-06-15 and works page update is 2026-03-16.
These are stored only as `source_page_updated`. `fecha`, `fecha_publicacion`,
`fecha_acuerdo` and `fecha_aprob` remain null: the parser does not read PDF dates.
PDF issue, signature and receipt dates are also not approval dates. Listings may
remain online beyond their public consultation period; this is a snapshot of
published dossiers, not proof of a currently open consultation, a construction
start or definitive approval. There is no full historical RPUC coverage.

Coordinates and geometry remain null. No municipal centroid, parcel guess or
random displacement is used.

## Verification and local evidence

- `.../venv/bin/python -m unittest municipio.test_el_papiol -v`: seven tests pass,
  covering document grouping/deduplication, identity, dates and provenance,
  planning versus works, pagination rejection, invalid/forms/login content,
  manifest configuration, disabled licences and full-snapshot updates.
- Real `ElPapiolAyuntamientoAdapter.backfill_proyectos` extraction: five records,
  74 linked documents (1 + 6 + 1 + 23 + 43). Both source captures are saved from
  the adapter's actual HTTP responses.
- A representative link from every dossier returned HTTP 200. All four PDF
  responses began with the PDF signature. Two large PDFs (Puigmadrona memory and
  photovoltaic memory) exceeded the separate 12 MB evidence-download bound;
  their downloads were explicitly stopped and no incomplete PDF was saved.
  This affects optional document captures, not inventory or attachment coverage.
  Only representative links were tested; all 74 attachments were not downloaded.
- Captured Sala Polivalent transmission and fire-prevention general-description
  PDFs were also converted locally with `pdftotext`. They substantiate project
  documentation; dates in them are not ingested as agreement dates.
- `evidence/proyectos.jsonl`, `evidence/validation.json`, HTML captures and sample
  PDFs/text are local review artifacts. Validation lists live record count,
  source URLs, document counts, representative-link checks and limitations.
  Evidence is not source code and is not to be committed.
