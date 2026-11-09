# Lloseta — INE 07029 — Illes Balears

Verified live on 2026-11-09 using
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Implemented one adapter, `municipio.adapters.lloseta:LlosetaAyuntamientoAdapter`.
This is a deliberately partial snapshot of genuine Lloseta planning/project
**documents**, published by the regional environmental authority. It is neither
an exhaustive municipal project catalogue nor a granted-licence register.
Scheduling and coordinate jitter are disabled; `publication_ready` is false.

## Source discovery

- Municipal official website: https://ajlloseta.net/ca . Its footer identifies
  Ajuntament de Lloseta, Pou Nou 3, 07360 Lloseta (Illes Balears), CIF P0702900B.
- https://ajlloseta.net/ca/arxius-i-documents/urbanisme-i-obres and
  https://ajlloseta.net/es/archivos-y-documentos/urbanismo-y-obras — HTTP 200.
  These link to the municipal electronic office's procedure documents:
  https://ajlloseta.sedelectronica.es/transparency/c4e25346-c810-400f-bba9-9d277aefa4d2/ .
  The latter returned application forms (licence application, prior communication,
  builder appointment, ICIO self-assessment and planning certificate request).
  None is a granted licence or a project record.
- https://ajlloseta.sedelectronica.es/transparency/ — HTTP 200. Its root exposes
  a folder “7. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT (24)” through Wicket
  callbacks, not ordinary dossier URLs. Anonymous callback attempts returned a
  blank response. That folder's 24 documents are **not** claimed as covered.
  No credentials or authenticated/private access were used.
- https://ajlloseta.net/ca/contractes — official procurement inventory, inspected
  during discovery. Procurement announcements alone were excluded.
- https://ajlloseta.net/es/node/1441 — historical municipal PGOU advance notice
  dated 2015-09-09. Discovery only; it is not evidence of a current approved PGOU
  and is outside the implemented inventory.
- https://www.caib.es/sites/serveiassessoramentambiental/ca/mapa/ — official regional
  site map, HTTP 200, links to the two Lloseta document dossiers below.
- **Implemented inventory:**
  https://www.caib.es/sites/serveiassessoramentambiental/ca/publicacio_de_documents_ambientals_en_tramitacia_davaluacia_simplificada/
  — HTTP 200. This is an actual document inventory for simplified environmental
  assessment, with a full HTML table, rather than a news feed. Its main content
  contains two Lloseta entries. Navigation duplicates are excluded.

`proyectos.source: ayuntamiento` selects the existing portal-adapter pipeline
convention; the manifest notes and every output record explicitly identify the
actual publisher as CAIB / Govern de les Illes Balears, not the municipality.
No shared schema, registry or dependency was changed.

## Live coverage and document grouping

1. **13a/2024 Centre de gestió de residus no perillosos T.M. Lloseta**:
   https://www.caib.es/sites/serveiassessoramentambiental/ca/13a2024_centre_de_gestia_de_residus_no_perillosos_tm_lloseta/
   — one EIA document, CAIB file ID **449484**. The captured PDF's first page
   identifies a real waste-management installation at Calle Margers 1, Lloseta,
   promoted by LV RECICLAMAS 2005, S.L.U., and a document month of January 2024.
   This is a physical project, not an assertion of public ownership, execution,
   environmental authorization or a granted municipal licence.
2. **55e/2025 MP 1/2024 NS de Lloseta per implantar ús turístic**:
   https://www.caib.es/sites/serveiassessoramentambiental/ca/55e2025_mp_12024_ns_de_lloseta_per_implantar_as_turastic/
   — four documents, retained together under the same environmental dossier:
   Estudi ambiental (**504791**), Estudi incidencia paisagtistica (**504803**),
   Memoria (**504792**), and Informe d’impacte directe i induït sobre el consum
   energètic i les emissions (**510231**). These are not four separate projects.
   The environmental dossier number 55e/2025 is not the planning modification
   number 1/2024; both remain visible in the title/identifier fields.

All five exact download URLs are retained in `documentos`, with their source
page and CAIB file ID. Local `evidence/validation.json` records those URLs,
HTTP status, PDF content type, byte count and SHA-256 for each downloaded file.
All five responses began with `%PDF-`. Captures are under `evidence/`.

## Semantics and limitations

- The adapter refreshes the complete single-page simplified-assessment inventory,
  selecting explicitly named Lloseta entries with actual environmental dossier
  identifiers. For table links pointing directly to a PDF, it finds the dossier
  from the site's real navigation links by the same identifier; it never guesses
  a dossier URL. Unsupported or ambiguous entries fail extraction.
- The source may retain documents after an assessment has concluded. Presence
  in this inventory is not a reliable current procedural phase. `fase` is null.
  In particular, the separate CAIB 2026 environmental-resolution inventory also
  lists an environmental report for MP1/2024:
  https://caib.es/sites/serveiassessoramentambiental/ca/publicacions_acords_autoritzacions_ambientals_2026/ .
  Environmental reports are not planning approval or licence grants. Resolutions
  and their later procedural history are outside this adapter's scope.
- Publication, agreement and approval dates are separate null fields: the
  dossier HTML provides none. Document months, years in expediente numbers,
  digital-signature dates and crawl time are not substituted for those dates.
- No project geometry is extracted. The waste EIA contains UTM coordinates and
  maps; their CRS and geometry have not been validated by this adapter. No
  conversion, centroid, fabricated coordinate or jitter is used. The HTML
  document inventory provides no verified georeferenced project geometry.
- Other municipal works, ordinary environmental assessment, environmental
  authorizations/resolutions, historical PGOU and the municipal transparency
  folder are not covered. The two records do not imply only two projects exist
  in Lloseta or that either project is still awaiting environmental assessment.
- The reviewed HTML inventory has no pagination. The adapter parses the entire
  table without a record cap or date cutoff. Next links, pagination containers
  or page/offset query parameters cause an explicit error. Changed headings,
  missing/ambiguous dossiers or missing documents also cause errors. HTTP
  errors, timeouts and the 8 MB HTML response limit fail rather than truncate.
  Output is replaced atomically only after all dossiers parse successfully.
- Document contents are retained through links; PDF text/geometry and subsequent
  resolutions are not parsed during routine extraction. Download verification
  in local evidence was performed separately after the real adapter run.

## Validation and reproduction

Parser tests (8 passed):

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_lloseta -v
```

Tests cover municipality/content scoping, navigation exclusion, direct-PDF
inventory entries, instrument/document grouping, stable identity, null date
semantics, paging rejection, ambiguous/wrong dossiers, external document
rejection, complete atomic refresh, manifest loading and disabled licences.

Real live extraction used `load_manifest('lloseta')`,
`load_portal_adapter(manifest)` and `adapter.backfill_proyectos(...)` with
`portal.config['capture_dir'] = 'evidence/live-captures'`. Result: **2 records,
5 documents**, with the registry's entity-policy annotation applied. The policy
reports both as unknown categories (2/2); they are not manually assigned an
unsupported downstream category. `publication_ready` remains false.

Local uncommitted evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`,
three adapter HTML captures under `evidence/live-captures/`, discovery HTML
captures and the five source PDFs named by CAIB file ID. The live runtime is
Python 3.12. No installation, database, publishing or deployment was needed.
