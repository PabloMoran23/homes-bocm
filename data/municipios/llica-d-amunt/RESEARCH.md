# Lliçà d'Amunt — Barcelona — INE 08107

Verified 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One municipal adapter, two current official inventories, partial municipal coverage.
Scheduling, licence extraction and coordinate jitter are disabled.

## Discovery and chosen sources

- [Municipal urbanism index](https://www.llicamunt.cat/seu-electronica/urbanisme)
  links directly to both inventories below, detail studies, acoustic maps and the
  centre development project. Capture: `evidence/urbanisme.html`.
- [Planejament urbanístic](https://www.llicamunt.cat/seu-electronica/urbanisme/planejament-urbanistic-)
  is an unpaginated, structured inventory explicitly describing current planning.
  Its page-update timestamp is 2026-07-10, not an instrument approval date.
  Extracted **10 instruments and 27 document links**: one POUM, five POUM
  modifications, Can Carreres special plan, PMU-6 Pinsos Tenes, Can Ballestà
  special plan and its modification. Capture: `evidence/planejament.html`.
- [Estudis de detall](https://www.llicamunt.cat/seu-electronica/urbanisme/estudis-de-detall)
  explicitly lists current studies complementary to municipal planning. All **30
  table rows** are extracted, from ED 1-77 to ED 1-09, with **90 document links**.
  Each row groups written, graphic and administrative documents under its actual
  dossier identifier and source address. The municipality calls these documents
  synthetic: full files require the OAC or municipal technical services. Its
  2018-05-10 page update is not an approval date. Capture: `evidence/estudis.html`.

## Other official sources inspected and scope boundaries

- [RPUC](https://dtes.gencat.cat/rpucportal/#/inici) is linked by the inventory as
  the place to consult the totality of current planning. This adapter does not
  crawl that register and therefore does not claim complete municipal coverage.
- [Centre development project](https://www.llicamunt.cat/seu-electronica/urbanisme/projecte-de-desenvolupament-del-centre-urba)
  describes a 2018 collaboration agreement and an older development proposal.
  [Current centre topic page](https://www.llicamunt.cat/temes/nou-centre-urba)
  links to construction phases and project information. Captured locally as
  `desenvolupament.html` and `centre.html`; neither is an additional feed here.
  The centre POUM modification already occurs in the chosen planning inventory.
- Acoustic maps, licence application forms, licence suspensions and unrelated
  news are not projects or granted licences. No procurement feed is used.
  No verified granted-licence inventory is claimed.

## Grouping, provenance and semantics

The POUM's norms, annex, twelve plans and three correction documents are grouped
as **one instrument with 17 links**, rather than individual projects. The PMU-6
BOPB announcement and full plan form one instrument with two links. The Can
Ballestà special plan and its separately named modification remain distinct.
POUM modifications remain separate instruments. Every document retains its
source title, exact resolved URL, inventory URL, section and available list-item
description. No PDF document is converted into a licence record.

Phases come only from the source's explicit current-inventory narrative or
definitive-approval heading/title. A modification without such an explicit
statement gets a null phase. There is no inference of construction progress.
Generic date, publication date, agreement date and approval date are all null:
the HTML supplies no instrument-specific dates and the adapter does not parse
PDF dates. Neither years in filenames nor dossier suffixes nor page timestamps
are promoted into dates. PDF evidence may contain additional dates that remain
outside this extraction's coverage.

Identity is a hash of the inventory plus actual dossier number for detail
studies, the source URL for other instruments, and explicit grouping keys for
POUM and PMU-6. Geometry and coordinates remain null; PDF maps are links, not
verified vector boundaries. `publication_ready` is false on all records.
There is no municipal-centroid substitution or invented location.

## Extraction and validation

Backfill and update fetch both full inventories and replace the JSONL snapshot
only after both parse successfully. There is no record-count cap or sliced table.
Pagination or continuation indicators cause an error instead of silent partial
output. Changed headings, table columns, incomplete dossiers or unsupported
document hosts also fail. HTTP errors and responses above 4 MB fail without
overwriting the last snapshot. Network requests use a 40-second timeout.

Parser tests:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_llica_d_amunt -v
```

Six tests cover grouping, separate modification identity, date semantics, missing
coordinates, stable PMU identity, 75-row extraction without truncation, changed
schemas, pagination, login/navigation-only content, unrelated forms, manifest
resolution, disabled licences and preservation of a prior snapshot on failure.

Live extraction uses `load_manifest`, `load_portal_adapter` and
`backfill_proyectos`, with source captures enabled. Expected reviewed inventory
snapshot, confirmed live: **40 genuine planning instruments, 117 document links**. Local evidence
includes `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/tests.txt`,
both source HTML files and representative original PDF captures. Validation
records the observed counts, capture hashes, document checks and limitations.
Legacy HTTP document URLs are retained as published; the availability of every
attachment is not verified. An optional capture of the large POUM norms exceeded
a 12 MB evidence bound and was abandoned; its link remains in the POUM record.

Evidence is local and excluded from source changes. No shared source, dependency,
credential, database, production, deployment or Git metadata changes are needed.
