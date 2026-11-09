# Artés — INE 08010, Barcelona, Catalunya

Verified anonymously on 2026-11-09. This adapter covers the municipal project/study
inventory and the published initial-approval POUM dossier. It does not cover all
municipal projects, works, historic planning instruments or granted licences.

## Official source discovery

- Municipal urban-planning area, HTTP 200:
  https://www.artes.cat/arees/157-urbanisme
  General service information, related plans and physical-works news. The service
  description itself is not a project. News listings are outside this adapter's
  inventory coverage; no procurement announcements or application forms become
  granted licences or project records.
- Official transparency urban-planning index, HTTP 200:
  https://seu-e.cat/ca/web/artes/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
  Links to the following inventories, inspected as live HTML:
  - https://seu-e.cat/ca/web/artes/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
    Provides RPUC/MUC discovery links, not individual dossiers in its HTML. The
    regional register's full municipal history is not extracted.
  - https://seu-e.cat/ca/web/artes/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/documents-en-tramit-198
    No instrument rows or document links in the inspected response. This is not
    evidence that the municipality has no instruments under consideration.
  - https://seu-e.cat/ca/web/artes/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-i-estudis-urbanistics-213
    Two actual, named instruments with municipal document links: roundabout and
    adjacent-area design at B-430/BV-4512; urban integration study for the Malrubí
    stream. Both are included. No approval or construction status is inferred
    from their appearance in the inventory. Its `Actualització: 13/10/2025` is
    recorded only as `fecha_actualizacion_fuente`, never as publication/approval.
- Municipal homepage, HTTP 200, https://www.artes.cat/ links directly to the
  municipality's participation subdomain for the initial-approval POUM:
  https://participa.artes.cat/poum/aprovacio-inicial-del-poum
  This is a substantive planning dossier, not a news headline. The narrative
  explicitly states the plenary initial approval on **21 March 2024**. Recorded
  as `fecha_acuerdo` and `fecha_aprob`, with `fase: aprobación inicial`.
  Publication date remains null: neither retrieval time nor the agreement date
  is substituted for DOGC publication. This is the phase of the extracted dossier,
  not an assertion that no later approval exists.
- Linked POUM document inventory, HTTP 200:
  https://participa.artes.cat/poum/aprovacio-inicial-del-poum/documentacio
  Twenty published SharePoint links (including two plan folders) are retained,
  together with the DOGC PDF link from the main dossier: **21 links in one POUM
  record**, not 21 independent projects. They cover memories, norms, catalogues,
  plans, reports and annexes. Each document retains its title, URL and referring
  municipal page. These public links are provenance; file contents, SharePoint
  availability and folder descendants have not been verified or enumerated.
  No authentication or credentials are used.

## Extraction behavior and limits

The live adapter fetches the three extraction pages above with HTTP status and
content-type checks, connection/read timeouts and a 5 MB response bound. Missing
inventory structure, empty results, missing POUM agreement text or missing POUM
supporting links fail before replacing the output. Project documents are grouped
per inventory list item, with repeated titles merged; the POUM has a stable identity
based on its dossier URL. The project/study identities use their source titles.
There is no hard-coded output record or crawl-time approval date.

All current inventory items and POUM document links are extracted. No pagination
was present in the inspected sources. Recognized next/previous links and paging
query parameters cause an explicit error, requiring crawler review instead of
silently returning the first page. Updates refresh this complete scoped snapshot;
`state_path` is not used as a date cutoff.

No verified project geometry is available from these HTML inventories. Coordinates
and geometry remain null; no municipal centroid or jitter is substituted.
`publication_ready` is false. Scheduling, missing-location jitter and licence
extraction are disabled in the manifest. A public licence register has not been
verified; forms and the POUM's licence-suspension text are not licence grants.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_artes -v`: **6 tests passed**. Tests cover document
  grouping, update-date semantics, explicit initial approval versus publication,
  pagination rejection, empty/form/navigation rejection, stable IDs, snapshot
  refresh, failure preserving prior output, manifest loading through the registry,
  and disabled licences.
- Live `load_manifest('artes')` → `load_portal_adapter` → `backfill_proyectos`:
  **3 actual records**, with document counts **1, 1, 21**.
- Local `evidence/proyectos.jsonl` contains the live records, including the registry's
  standard entity-policy annotation. `evidence/validation.json` contains live count,
  source URLs, limitations, extraction timestamp and test result. The three exact
  extraction responses are saved as `live_inventory.html`, `live_poum.html`, and
  `live_poum_documents.html`. Discovery captures are also under `evidence/`.
- Evidence is local, excluded from the four source-file deliverables. No shared
  sources, dependencies, database, deployment, credentials or remote git operations
  were used.
