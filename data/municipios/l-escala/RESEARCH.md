# L'Escala — Girona — INE 17062

Verified 2026-11-07 using the preinstalled Python 3.12 virtual environment.
This adapter extracts a **partial municipal planning inventory**, not the complete
municipal project history. Six real instruments retain thirteen document URLs.
Scheduled ingestion, missing-coordinate jitter and licences are disabled.

## Official inventories discovered

- Municipal urbanism entry: https://www.lescala.cat/ca/urbanisme/ — HTTP 200;
  directs users to the official transparency portal.
- Official urbanism index:
  https://seu-e.cat/ca/web/escala/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
  — HTTP 200; links separately to planning, planning in progress and projects.
- **Implemented inventory**:
  https://seu-e.cat/ca/web/escala/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200; visible source update 28/09/2026. It contains the SUP-IV
  Recs-Dunes-Puig PGOU modification, reference-ground/floor-level PGOU
  modification, hotel-use PGOU modification, Horta Vella partial plan,
  Estany de Poma PGOU modification, and special heritage protection plan/catalogue.
  Documents are grouped by the page's nested list hierarchy. The two Estany
  de Poma entries (drawings and memory/rules/annexes) form one instrument.
- https://seu-e.cat/ca/web/escala/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-193
  — HTTP 200; current, substantial physical-project document inventory, updated
  06/11/2026. Includes pool repairs, municipal buildings, streets and other works.
  **Discovered but not implemented** in this narrowly scoped planning adapter;
  this is a material coverage limitation, not an unavailable source.
- https://seu-e.cat/ca/web/escala/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic-en-tramitacio-220
  — HTTP 200; says “En construcció”, no extractable instruments.
- https://www.lescala.cat/ca/poum-pla-dordenacio-urbana-municipal/
  — HTTP 200; older POUM revision timeline with geological, mobility and
  environmental studies. The new revision must not be represented as the
  definitively approved 1993 general plan. Outside implemented inventory scope.
- https://poum.lescala.cat/ — linked official microsite; live requests failed
  certificate-chain verification. No TLS bypass used. The “POUM EN REVISIÓ”
  navigation link alone is not emitted as an additional instrument.

## Extraction contract and provenance

One complete GET of the planning inventory, with TLS verification, HTTP errors,
40-second timeout and a 3 MB response limit. No pagination is present in the
reviewed inventory. Pagination markers cause an explicit error; all supported
entries are processed with no row cap. Unknown document-bearing items,
unrecognized list entries, empty content or documents outside a recognized
group cause an error before output is replaced. Incremental extraction refreshes
the full inventory snapshot; it makes no historical completeness claim.

Only official municipal `/documents/2475467/` links are admitted as documents.
Nested annexes and duplicate anchors remain in their parent instrument; duplicate
URLs collapse. Every document retains its title, original resolved URL and
inventory provenance. Document bodies have not been downloaded or parsed; their
content and legal currency are not certified by this adapter.

The hotel-use mobility study has a malformed source href
`http://Estudi d'avaluació de la mobilitat generada`. It is retained verbatim in
`enlaces_no_documentales`, not repaired or treated as a usable document URL.
The regional map navigation link is also excluded as a record.

No approval, agreement or publication date is established by the inventory.
Those fields and generic `fecha` remain null. `fecha_actualizacion_fuente`
records the inventory update separately. “Aprovar inicialment” wording is
preserved in source titles, without inferring a legal phase or definitive
approval. Dates in PDF filenames are not used as approval dates.

No verified instrument geometry is extracted. Coordinates and geometry remain
null and `publication_ready` is false. No municipal centroid or fabricated
location is substituted. No public register of granted licences was verified;
application forms and procurement notices are not licence/project records.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_l_escala`: four tests pass. Tests cover nested
  annex grouping, Estany de Poma grouping, duplicate anchors, malformed link
  provenance, date semantics, rejected unrelated content, pagination rejection,
  manifest loading and disabled licences without network calls.
- Direct live `LEscalaAyuntamientoAdapter.backfill_proyectos`: six records,
  thirteen document links; all six have null geometry and no inferred dates.
- Local `evidence/proyectos.jsonl`, `evidence/validation.json` and
  `evidence/planejament-live.html` record the actual extraction. Other discovery
  HTML captures include the separate project inventory and the empty
  in-progress inventory. Evidence is local, not source to commit.

No shared files, dependencies, credentials, external workspaces, database or
publishing/deployment services were used or changed.
