# Vilafant — INE 17221, Girona

Live verification: 2026-11-09. Exactly one municipal adapter, with deliberately
partial coverage. Scheduled ingestion and missing-coordinate jitter are disabled;
licences are disabled. All 24 extracted records have `publication_ready: false`.

## Official sources discovered

- Municipal urbanism landing page: https://www.vilafant.cat/per-temes/urbanisme
- Extracted inventory (HTTP 200): https://www.vilafant.cat/per-temes/urbanisme/planejament-en-tramit
  The `2024 endavant` section currently names the May 2025 reurbanisation and
  service improvements on carrer Almogàvers, with a presentation and direct
  e-Tauler dossier link. The `2020-23` section lists actual works and planning
  instruments with documentary links. Its label is a municipal grouping, not
  proof that every document was published in those years.
- Current notice board linked by the municipality:
  https://tauler.seu-e.cat/inici?idEns=1722140003
  and the Almogàvers detail:
  https://tauler.seu-e.cat/detall?idEns=1722140003&idEdicte=1722140003_557187
  Both HTTP 200 responses are JavaScript application shells, without notice
  records in the response HTML. Neither is represented as a complete harvested
  inventory. The municipal inventory explicitly redirects 2024-onwards enquiries
  to this board; modern coverage is therefore incomplete.
- Public planning inventory hub (HTTP 200):
  https://www.vilafant.cat/per-temes/urbanisme/publicitat-planejament-general-i-gestio-urbanistica
  Its following inventories were also fetched successfully and captured, but are
  **not harvested** by this adapter:
  - [General planning](https://www.vilafant.cat/per-temes/urbanisme/publicitat-planejament-general-i-gestio-urbanistica/planejament-general): municipal general plan and amendments, with mixed publication/agreement narratives.
  - [Derived planning](https://www.vilafant.cat/per-temes/urbanisme/publicitat-planejament-general-i-gestio-urbanistica/planejament-derivat): special/partial plans, modifications, urbanisation instruments.
  - [Reparcellations](https://www.vilafant.cat/per-temes/urbanisme/publicitat-planejament-general-i-gestio-urbanistica/reparcel-lacions): Poliesports and Pont del Príncep instruments.
  - [Urban management](https://www.vilafant.cat/per-temes/urbanisme/publicitat-planejament-general-i-gestio-urbanistica/gestio-urbanistica): Sant Cebrià urbanisation and Sol i Vent road improvements among other procedures.
  - [Virtual planning register](https://www.vilafant.cat/per-temes/urbanisme/publicitat-planejament-general-i-gestio-urbanistica/registre-virtual-de-planejament-urbanistic-de-vilafant): outbound Generalitat register link, not itself a list of projects.
- https://www.vilafant.cat/per-temes/urbanisme/sol-licituts-instancies-urbanisme
  contains application forms and procedures, not a verified register of granted
  licences. Search discovery confirmed this distinction; no licence is emitted.

## Extraction semantics and bounds

The adapter fetches the complete municipal inventory HTML, bounded at 3 MB with
connection/read timeouts. It requires the three reviewed section headings and
rejects pagination signals rather than silently return the first page. It parses
all supported work/planning heading blocks throughout the `2020-23` section and
named reurbanisation entries in the modern complementary-document list. The
`2013-19` archive is intentionally excluded by section, not by row-count limits.
Licence suspensions, application requests, acoustic maps and unrelated navigation
are excluded. No procurement announcements or generic news become projects.

A block is one instrument, not one record per PDF. Document URLs, anchor labels,
full surrounding source labels and municipal provenance are retained, including
municipally endorsed Google Drive links and e-Tauler links. The live snapshot has
24 instruments, 71 document links, and 13 explicit municipal expediente references.
Links are not downloaded or authenticated; their current contents and availability
have not been independently checked. The modern Almogàvers row is supported by
the municipality's own named project and documentary links, not by parsing the
notice board shell.

Only dates explicitly labelled BOP/DOGC in document anchor text are parsed as
`documentos[].fecha_publicacion` (34 dates in this snapshot). Publication is not
an approval/agreement date. Project-level generic/publication/agreement/approval
dates and phase remain null because mixed stages and document dates do not
establish one unambiguous project-level event. Narrative date evidence remains
verbatim in descriptions/document context for future review. The 2023 expediente
blocks contain bulletin labels dated 2022 in the source; these are preserved,
not corrected or used as agreement dates. Invalid calendar dates return null.
"Maig 2025" is not converted into an invented day.

Identity is based on the explicit expediente, otherwise on the normalized named
instrument; repeated expediente blocks merge their document links. No cadastral,
municipal-centroid or approximate coordinates are supplied. Update refreshes the
same scoped snapshot in full and does not advance a potentially lossy date cursor.

The existing shared entity policy recognizes 13 referenced records and leaves 11
without a recognized expediente pending (`unknown_entity_spike` incident in the
local report). This is disclosed, not bypassed by invented references. These are
real source-backed records awaiting independent review, not publication-ready
activity records. Shared policy files have not been changed.

## Verification and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_vilafant -v`: six tests pass. Tests cover grouping,
  repeated instruments, publication versus deadline/agreement semantics, source
  label anomalies, current works, archive/form/news exclusion, empty or changed
  source rejection, pagination rejection, manifest loading, disabled licences and
  update delegation.
- Real `load_manifest('vilafant')` / `load_portal_adapter(...)` /
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 24 live records.
- `evidence/validation.json`: count, extraction time, source URLs, limitations and
  actual shared-policy outcome. `evidence/proyectos.entities.json` records that
  policy report. `evidence/inventory.html` captures the extraction response;
  additional HTML captures document the inventories and notice-board shells.
- Evidence is local only. Only the four requested source files are added. No
  dependency, shared-source, credentials, database, deployment or git metadata
  changes are part of this work.
