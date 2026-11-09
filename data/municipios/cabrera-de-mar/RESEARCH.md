# Cabrera de Mar — INE 08029, Barcelona

Verified on 2026-11-09 using the preinstalled virtualenv Python. This adapter
extracts a deliberately partial municipal snapshot: **10 real planning instruments**
from the official current-planning inventory, retaining **19 document/register
links**, grouped by instrument. No granted licences or physical execution claims
are made. Scheduling and missing-coordinate jitter are disabled.

## Official source discovery

- Urbanism index: https://www.cabrerademar.cat/ajuntament/normativa/179-urbanisme
  links to current planning, the geographic viewer, public exhibition and an
  industrial-roof provisional-use project. An index or service description is
  not itself a project record.
- Implemented inventory: https://www.cabrerademar.cat/ajuntament/normativa/179-urbanisme/planejament-vigent
  contains the POUM, POUM modifications, derived planning, an acoustic map and
  the Sant Vicenç modification. The crawler follows its descendant menu links
  recursively, excluding the acoustic map. All 15 planning index/detail pages
  were fetched successfully; no pagination appeared in the reviewed tree.
- POUM: https://www.cabrerademar.cat/ajuntament/normativa/179-urbanisme/planejament-vigent/poum
  groups the municipal normative PDF, zoning-map PDF and RPUC dossier 245109.
- Modification inventory: https://www.cabrerademar.cat/ajuntament/normativa/179-urbanisme/planejament-vigent/modificacions-poum
  supplies five instruments: Can Serra, Cooperativa/Cal Conde, Escola Pla de
  l'Avellà, Ca l'Arnau/Can Mateu/Can Rodon, and normative correction in zone 8.
  Can Serra's two PDFs remain one record. Sant Vicenç is a sixth modification
  linked directly from the current-planning root, also captured.
- Derived planning: https://www.cabrerademar.cat/ajuntament/normativa/179-urbanisme/planejament-vigent/planejament-derivat
  branches to special plans and urban improvement plans: educational equipment,
  tourist-use housing and PA-3 La Pineda-1. The tourist-use plan's plan PDF,
  plenary certificate, DOGC PDF and RPUC dossier remain one instrument.
- Additional inventory discovered, outside implemented coverage:
  https://www.cabrerademar.cat/ajuntament/normativa/179-urbanisme/exposicio-publica-projectes-i-planejament
  lists Can Rodon and Ca l'Avelino provisional parking uses, compensation-board
  statutes, the B-502 pedestrian/cycle itinerary and Rambla dels Vinyals torrent
  project. The B-502 page was inspected; its content container was empty, while
  documents elsewhere in this CMS can appear in separate page-documents sections.
  No conclusion about approval or construction is inferred from this listing.

## Provenance and semantics

Stable IDs hash the actual instrument detail URL, never document filenames or
crawl position. Responsive duplicate menus and repeated document links are
collapsed. Each document keeps its label, absolute URL and source detail page.
The `POUM` title is preserved as published. No RPUC identifier is misrepresented
as a municipal expediente number. PDFs and RPUC dossier contents are not parsed
or independently validated; their links are provenance, not extracted agreements.

`fase=vigente` records the municipality's inventory classification, with
`fase_provenance` pointing to that inventory. It does not assert an independently
verified definitive approval. All agreement, approval and publication dates remain
null. `fecha_actualizacion_pagina` is explicitly separate: page updates in 2025
are neither instrument approvals nor gazette publication dates. Even the date in
the POUM PDF filename is not promoted to a verified publication date.

No verified project geometry was extracted. Coordinates and geometry remain null;
`publication_ready=false`. The shared entity-policy wrapper classified these
Catalan planning resources as `pendiente` (10 unknown, `adapter_incident` /
`unknown_entity_spike`); its existing rules require additional identity evidence
and do not recognize these planning-resource records. This is retained explicitly
in local validation, not bypassed with fabricated expediente IDs or grants. The
scraper is reviewable but these records are not ready for activity publication.

## Implementation and validation

The crawler completes the selected planning tree, rather than silently limiting
rows. Unexpected pagination fails explicitly. A 100-page safety bound, missing
content, unsupported leaf category, redirect, oversized response, missing source
documents or HTTP error aborts extraction before replacing the previous snapshot.
Updates refresh the same complete selected inventory. Licences return disabled.
The acoustic map and inventories outside current planning are explicit exclusions.

Commands run with
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`:

- `-m unittest municipio.test_cabrera_de_mar -v`: five tests passed, covering
  document grouping, date separation, navigation/form rejection, pagination,
  complete traversal with duplicate menus and preservation on failure.
- Live `load_manifest('cabrera-de-mar')` / `load_portal_adapter(...)` /
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 10 unique instruments,
  19 retained source links, 15 captured HTML pages. Manifest safety flags and
  municipality identity checked.

Local evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/proyectos.entities.json`, and HTML captures plus a URL-to-capture index
under `evidence/captures/`. Evidence is local and must not be committed.
