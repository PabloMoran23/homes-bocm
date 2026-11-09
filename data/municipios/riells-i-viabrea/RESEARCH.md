# Riells i Viabrea — INE 17146, Girona

Verified live on 2026-11-09 using the preinstalled batch Python runtime. This
adapter covers the municipality's current visible public-project inventory:
11 instruments, 25 document links. It is a partial documentary snapshot, not a
complete historical register or a granted-licence dataset. Scheduling and
coordinate jitter are disabled. All records have `publication_ready: false`.

## Official source discovery

- [Municipal technical services](https://riellsiviabrea.cat/cataleg-de-serveis/serveis-tecnics/)
  returned HTTP 200. It links to the official transparency planning section,
  the general RPUC search, and separate municipal pages for Can Salvà II,
  Ordenació urbanisation and Junior Park green-space amendments. These separate
  pages are outside the implemented inventory's scope; no full coverage claimed.
- [Official public-project inventory](https://seu-e.cat/ca/web/riellsiviabrea/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/informacio-publica-projectes-199)
  returned HTTP 200 with actual named instruments and municipality-owned PDF
  links in collection `/documents/663872/13265083/`. This is the extraction source.
  The visible footer says updated 22/09/2026; that is page maintenance metadata.
  No inventory pagination was present. The scraper reads all visible entries
  and fails if pagination controls appear rather than silently taking page one.
- [Official planning section](https://seu-e.cat/ca/web/riellsiviabrea/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic)
  returned HTTP 200, but its journal articles exposed explanatory planning text
  rather than document-backed instrument rows. Not treated as project data.
- The municipality links to `https://dtes.gencat.cat/rpucportal/#/consulta/cerca`,
  a general register search rather than a municipality-specific dossier.
  This adapter does not turn that navigation link into a POUM record.

## Records and grouping

The eleven extracted instruments are Pinetell geotechnical stabilisation;
conversion of municipal pavilion space to SAIAR; municipal warehouse solar
installation; POUM amendment regulating open-space/equipment uses; Plemen PAa-3
reparcelling; Pla del Mercat PAa-2 reparcelling revision; Plemen PAa-3 urbanisation;
the rural-land telecommunications specific-action project (ADAMO); Collformic
slope environmental restoration; Plaça del Mercat paving; and POUM amendment 3
around Barri de l'Estació. The telecommunications proposal is a physical network
project with technical and landscape documents, not an assertion of a granted
licence or public ownership.

Sibling links stay with one instrument: SAIAR project/addendum; Mercat project/
plans; Plemen agreement, notice, technical document and component plans;
telecommunications project/landscape study; paving project/plan. Links and link
labels retain provenance; relative URLs resolve against the official portal.
Commented-out withdrawn content is excluded. Ordinances, pricing reports,
water-service regulations and service-establishment reports, and licence
suspensions are excluded. An unlinked PAa-2 urbanisation paragraph is not emitted.

### Verified Plemen source-label discrepancy

The inventory's PAa-2 Plemen reparcelling link has UUID
`33abae7d-fda3-4af6-b9c3-b4fb0495a269`. Its actual PDF cover explicitly says
**PA a3-PLEMEN**, July 2024. The linked document is 80,477,635 bytes; downloaded
locally and its first three pages extracted with preinstalled `pdftotext`.
It is grouped with the PAa-3 instrument rather than fabricated as a second PAa-2
project. Both original page titles remain in `titulos_fuente`, with a conflict
note in `nota_fuente`. The alias is tied to the two verified document UUIDs,
not a broad fuzzy match on the sector name. Urbanisation remains a separate
instrument from reparcelling.

The PAa-3 agreement UUID `3fd9dc10-1147-4b75-9ef0-6a665b2f34ca` is an actual
Junta de Govern agreement, session 29 June 2022, expediente X2022000756.
Its full 302,050-byte PDF and first three pages of extracted text are captured.
These manual checks establish the grouping; the runtime parser does not parse
PDF bodies or copy these agreement metadata into its page-derived records.
The 2024 technical revision and 2022 agreement are retained within one instrument
without claiming the 2022 approval applies to every later document version.

## Semantics and operational limits

`fase` is populated only when initial approval is explicit in the instrument
title or its document labels. A section called public exposure or urbanisation
does not establish approval. All exact date fields remain null: November 2025
and June 2025 are partial dates, filenames are not publication dates, and the
2014 POUM approval/publication dates in an amendment's background belong to the
parent plan. Descriptions and source titles retain this text without assigning
it to the amendment's dates. No subsequent or definitive approval is inferred.

Identity derives from an official primary document UUID, never an invented
expediente. Grouped records declare `source_entity_type: documento`: registry
entity policy classifies them as documentary resources, not activity-eligible
verified dossiers. No coordinates, centroid, geocoder result or geometry are
substituted. All geometry fields are null. The repository's shared policy and
dependencies are unchanged.

Backfill fetches the complete static inventory, parses visible sibling blocks,
groups document versions and writes JSONL atomically. Update refreshes that
snapshot; there is no historical cursor or claim to detect removed entries.
HTTP errors, an unexpected redirect host, missing inventory, foreign document
collections, pagination, or oversized responses fail rather than emit placeholder
records. The 4 MB inventory bound raises an error instead of truncating.
Licence methods explicitly return disabled and write no licence records.

## Validation and evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```text
python -m unittest municipio.test_riells_i_viabrea -v
8 tests passed
```

Tests cover grouped addenda/plans and alias deduplication, paragraph-based
reparcelling entries, the verified Plemen alias, unrelated/hidden exclusions,
date leakage, rejected pagination/foreign sources/login markup, manifest
resolution, disabled licences, snapshot updates and preservation of prior
output on invalid responses.

Live extraction uses `load_manifest`, `load_portal_adapter`, then
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Result: 11 records,
25 retained links, entity-policy status `ok`, zero invented dates/coordinates.
Primary document requests for all twelve original page entries returned HTTP
200, `application/pdf`, and a `%PDF-` signature; after grouping these cover the
eleven instruments. Other attachment links are retained but not all downloaded.

Local evidence (not committed): `evidence/proyectos.jsonl`, `validation.json`,
`inventory.html`, discovery captures `services.html`, `planning.html` and
`projects.html`; PDF signature prefixes; complete `plemen-4.pdf` and
`plemen-6.pdf` with their text extracts. Validation records source URLs,
live record count, link checks, limitations and test outcome. Prefix captures
are explicitly partial and are not presented as complete PDFs.
