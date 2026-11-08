# Alella — INE 08003, Barcelona, Catalunya

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One municipal adapter implements a complete snapshot of the currently advertised
**works-project inventory**, with deliberately partial municipal coverage. It does
not implement a granted-licence register or claim complete planning coverage.
Scheduling and coordinate jitter are disabled. All records have
`publication_ready: false` because no project geometry was verified.

## Official source discovery

- Municipal urbanism entry: https://alella.cat/urbanisme links to municipal works
  projects, planning, and licence procedures. Licence application procedures and
  forms are not evidence of granted licences and are excluded.
- Works inventory: https://alella.cat/seccio.php?id=68 and its linked canonical
  listing https://alella.cat/fitxes.php?id=68 returned HTTP 200 and the same eight
  named projects. The scraper uses `fitxes.php`, follows all advertised inventory
  page links and fetches each listed project detail. The live listing has no next
  page, page count, or pagination form. Fragment-only navigation is not pagination.
- Current planning inventory: https://alella.cat/pagina.php?id=24216 returned
  HTTP 200, headed `PLANEJAMENT VIGENT`, with page publication 2026-09-02. It lists
  the POUM, amendments, special plans and ordinances. This separate inventory is
  **not extracted by this adapter**. Its page date is not an instrument approval
  date. Some entries describe annulment or suspension and two sports-pavilion
  planning entries state different May 2025 approval days; no resolution of that
  discrepancy or invented merged planning record is attempted.
- Regional RPUC links on that page are supporting planning-register references,
  not a fetched geometry source. Procurement notices, related news and procedure
  links are not collected as projects.

## Extracted works and date semantics

Each title below links to a concrete municipal project fiche, not an announcement
standing alone. `documentos` groups all links from the fiche's labelled fields,
including agreement notices, memoranda and drawings. Duplicate PDF thumbnail and
filename links produce one document entry. Related-content links outside those
fields are excluded. Stable IDs use the actual municipal fiche ID.

| Fiche | Project | Fiche publication | Initial approval | Definitive approval | Documents |
| --- | --- | --- | --- | --- | --- |
| [25951](https://alella.cat/fitxa.php?id=25951) | Reforma i ampliació de Can Gaza | 2026-10-06 | 2026-03-12 | 2026-10-01 | 3 |
| [25600](https://alella.cat/fitxa.php?id=25600) | Urbanització del sector Crison | 2026-01-28 | 2024-03-28 | 2026-01-08 | 4 |
| [25311](https://alella.cat/fitxa.php?id=25311) | Reurbanització Bellaterra i Bellavista | 2026-01-12 | 2025-10-23 | 2026-01-08 | 2 |
| [25310](https://alella.cat/fitxa.php?id=25310) | Senyalització Mas Coll, Alella Parc i Can Comulada | 2026-01-12 | 2025-11-06 | 2026-01-08 | 5 |
| [25495](https://alella.cat/fitxa.php?id=25495) | Rehabilitació pis 1r 1a Casa dels Mestres | 2026-01-08 | 2025-09-25 | 2025-12-18 | 2 |
| [23694](https://alella.cat/fitxa.php?id=23694) | Cobertura i tancament parcial pista exterior pavelló | 2025-06-10 | 2025-03-20 | 2025-06-05 | 3 |
| [23069](https://alella.cat/fitxa.php?id=23069) | Avantprojecte reurbanització del Rost | 2024-11-07 | — | — | 3 |
| [21756](https://alella.cat/fitxa.php?id=21756) | Urbanització PAU 14 La Gaietana | 2024-04-11 | 2024-03-28 | — | 3 |

The fiche's labelled publication is `fecha_publicacion`; the separate labelled
BOPB announcement date is `fecha_anuncio_bopb`. For example, Can Gaza has BOPB
announcement 2026-03-25, distinct from both approval dates and the later fiche
publication. Initial and definitive approvals have separate explicit fields;
`fecha_aprob` is definitive when present, otherwise initial. Generic `fecha`
remains null. Narrative dates about accompanying instruments do not override the
project's labelled approval fields. Raw field names and text remain in
`source_fields`; the source's `Descripció` remains `descripcion`. Can Gaza uses
`Nom del projecte` for its narrative; that narrative remains under its original
field instead of silently becoming a description. Rost is an anteproject with no
asserted approval date. The three explicit `En execució` subtitles are retained
as source-reported phases, without independent verification of execution.

Documents are retained with their original href, resolved URL, label, source field
and fiche URL. None are downloaded or interpreted. Crison's source contains a
malformed `Ahttps://...` href, retained and flagged without inventing a corrected
URL, plus a publicly embedded signed download URL whose timestamp/expiry is old.
That URL is marked as expiring and not fetched; it is not used to obtain access.
The properly formed announcement link in `Data anunci BOPB` is also retained.
Document links are evidence of provenance, not a claim that every download works
or that its text has been verified. Large linked project PDFs are not necessary
for extracting the labelled fiche data.

## Validation and failure handling

- `python -m unittest municipio.test_alella -v`: **8 tests passed**. Offline fixtures
  check separate date meanings, absent approvals, narrative-date exclusion,
  execution phase, document grouping, malformed links, licence-form exclusion,
  missing/mismatched pages, multi-page traversal, repeated-page detection and
  preservation of the previous output on extraction failure.
- Actual `AlellaAyuntamientoAdapter.backfill_proyectos` live run: **8 records**,
  **25 document links**, one inventory page and eight detail requests, all HTTP
  200. No inferred coordinates, dates or records. Eight distinct project IDs.
- Local `evidence/proyectos.jsonl` contains actual live output;
  `evidence/validation.json` contains `live_records`, all extraction `source_urls`,
  limitations, runtime, checks and HTTP capture metadata with SHA-256 hashes.
  HTML captures include the discovered inventories and project fiches. Evidence
  is local and is not a source change to commit.

HTTP requests have a 40-second timeout and a 4 MB response limit; oversized
responses raise instead of truncating. Empty or changed inventories, unexpected
records, missing project documents, conflicting dates, unrecognized pagination
and repeated pages fail the run. Pagination has a 100-page safety bound that
raises without writing partial output. All details must succeed before output is
written. Updates refresh the complete current inventory; no historical or
incremental-completeness claim is made.

Municipal, parcel and street centroids are not substituted for project geometry.
No granted licences, completed works, full municipal historical coverage, or
publication readiness are implied by this extraction.
