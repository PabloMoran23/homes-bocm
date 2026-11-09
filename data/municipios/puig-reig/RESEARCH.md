# Puig-reig — INE 08175, Barcelona, Catalunya

Verified live 2026-11-09 using the preinstalled Python runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts a **partial municipal document inventory**: 15 real named
planning instruments and projects with 15 source links. It does not establish
that each project has been approved, built or remains at the listed phase.
`publication_ready` is false; scheduling, coordinate jitter and licences are disabled.

## Discovery and official inventories

The municipal urbanism page https://puig-reig.cat/tramits/urbanisme/ is indexed
with the POUM and PPU-3 documentation, but direct requests to both bare and www
hosts closed the connection in this environment. It is not a runtime dependency.
The municipality's official transparency portal provides usable HTML inventories:

- Discovery index: https://www.seu-e.cat/ca/web/puig-reig/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
- Planning: https://www.seu-e.cat/ca/web/puig-reig/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — 3 instruments: POUM 2023, Pla parcial del PPU-3, and the POUM modification
  around the football ground. Footer update: 2025-06-06.
- Urbanization: https://www.seu-e.cat/ca/web/puig-reig/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-d-urbanitzacio-199
  — 4 projects: Viladomiu-Cal Marçal services, PPU-3 El Saltet and cemetery,
  PAU-19 Les Abelles-La Parada, and services to the Reynolds factory access road.
  Footer update: 2025-09-23.
- Local public works: https://www.seu-e.cat/ca/web/puig-reig/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-d-obra-local-202
  — 4 projects: Puig-reig–Viver i Serrateix road maintenance (2025 phase 2),
  Cal Sastre de la Costa consolidation and rehabilitation, demolition and
  reurbanization at C/ del Torrent 10, and athletics track and football ground.
  Footer update: 2025-04-09. Years/months in titles are retained as title text.
- Reparcelling: https://www.seu-e.cat/ca/web/puig-reig/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-de-reparcel-lacio-198
  — 3 instruments: Colònia Marçal-Viladomiu, voluntary PPU-3 El Saltet, and
  PAU-19 Les Abelles-La Parada. Footer update: 2025-09-23.
- Specific action: https://www.seu-e.cat/ca/web/puig-reig/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-d-actuacio-especifica-197
  — 1 PAE/project for extending the Soler del Jaumas quarry. It is not represented
  as a public works contract or a granted licence. Footer update: 2025-01-20.

All five runtime inventories returned HTTP 200 (www redirects to seu-e.cat:443).
The guessed unsuffixed `projectes-d-obra-local` URL returned 404; the actual
`-202` URL was discovered from the urbanism index. No procurement notices,
application forms, political mandate proposals or unrelated news become records.

## Semantics, grouping and coverage

The POUM links to the official RPUC dossier:
https://dtes.gencat.cat/rpucportal/#/consulta/cercaPublic?%20reqCode=veureFitxa&codiPublic=2016%2F60771%2FN&assentament=101450&set-locale=ca
The other 14 links are municipal PDF documents under
`https://www.seu-e.cat/documents/2846680/`. The adapter records the actual links,
link labels and source inventory URL; it does not download/parse the PDFs or
query RPUC. No dossier number is invented from a scraper hash or document UUID.

A top-level instrument and its nested document links produce one record.
The generic `Plans parcials` heading is expanded to its named instruments.
Duplicate titles within an inventory merge their document links. Planning,
urbanization and reparcelling at PPU-3 or PAU-19 are distinct legal instruments,
not duplicate attachments of a single instrument. Identifiers hash inventory and
normalized instrument title; changing a title can change identity.

`fecha_actualizacion_fuente` is only the inventory footer date. Generic `fecha`,
`fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` remain null. The initial
approval label on the football-ground amendment is recorded as a document phase,
with an explicit scope caveat; it does not claim that this is its latest legal
status. Later agreements may exist outside these snapshots. Full historical
coverage, minutes, gazettes and later RPUC versions have not been extracted.

These pages provide no verified project coordinates. Coordinates and geometry
remain null. `source_entity_type: documento` accurately describes the evidence
level. The shared entity policy classifies all 15 as documents without activity
identity, with no unknown spike and no activity-publication eligibility. This
scraper is ready for independent review of its limited document coverage, not
for publishing activity or map records. No shared policy was changed.

## Runtime and validation

The adapter fetches all five inventories on every backfill/update. Each request
has connect/read timeouts and a 5 MB response limit. Pagination controls cause
an explicit error rather than silently dropping later pages. Missing inventory
structure, empty lists, unknown entry types, missing documents and unreviewed
external document targets also fail. Output is replaced only after every source
has parsed successfully. The existing snapshot survives a source failure.

- `python -m unittest municipio.test_puig_reig -v`: 7 offline tests passed.
  Tests cover date semantics, nested/multiple-document grouping, category
  expansion, duplicate identity, RPUC provenance, pagination, rejection of
  forms/login/navigation/foreign documents, failed-fetch snapshot preservation,
  entity-policy classification and manifest loading.
- Real live extraction through `load_portal_adapter(load_manifest('puig-reig'))`
  and `backfill_proyectos`: 15 records, 15 unique IDs, 15 document links,
  all geometry null. No licences extracted.
- Local uncommitted evidence: `evidence/proyectos.jsonl`,
  `evidence/validation.json`, shared entity-policy report, and five full source
  HTML captures named after the inventory URL slugs. Discovery captures are
  also retained under `evidence/`.

No dependencies or shared sources were changed. No credentials, databases,
GitHub, deployment, publish, synchronization or git mutation commands were used.
