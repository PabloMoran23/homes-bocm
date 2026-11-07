# Arenys de Mar — INE 08006, Barcelona, Catalunya

Verified live on 2026-11-07. One municipal adapter implements a complete snapshot
of the **Planejament general** inventory, not complete municipal urbanism coverage.
The live result is **9 planning instruments and 83 attached PDF links**, grouped
as one record per municipal instrument page. No granted licences are extracted.
Scheduling and missing-coordinate jitter are disabled. All records have null
coordinates/geometry and `publication_ready: false`.

## Official source discovery

- https://arenysdemar.cat/regidoria.php?id=40 — municipal Urbanisme, Obres i
  Serveis index. Its Planejament General link (`ambit.php?id=141`) resolves to
  https://arenysdemar.cat/fitxes.php?categoria=368, the actual extraction inventory.
- https://arenysdemar.cat/fitxes.php?categoria=368 — HTTP 200, municipal normative
  inventory with POUM and eight numbered modifications. All nine detail pages
  were fetched live and validated; no pagination controls were present.
- https://arenysdemar.cat/ambit.php?id=142 — derived-planning page linking a port
  special plan. Outside this adapter's explicitly limited general-planning scope.
- https://arenysdemar.cat/fitxes.php?categoria=158 — broader Projectes urbanístics
  notice inventory, inspected and captured as `evidence/inventory.html`. It mixes
  actual projects with housing allocation notices, authorisations, agreements and
  licence applications. Not extracted by this adapter. It contains newer notices
  than the general-planning inventory, so category 368 must not be represented as
  the entire or necessarily latest planning history of the municipality.
- https://arenysdemar.cat/fitxa.php?id=49415 — example of a newer POUM modification
  notice (Salines Bareu Tronqueda) in that broader inventory. Outside scope; its
  attachments are not merged into the general-planning snapshot.
- https://www.seu-e.cat/web/arenysdemar/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — transparency page points users to the RPUC municipal search rather than
  exposing its own complete instrument inventory. Not used as record data.

## Extracted instruments

| Municipal page ID | Instrument | DOGC publication as labelled by municipality | PDF links |
| --- | --- | --- | --- |
| 46633 | POUM | 2014-02-03 | 23 |
| 45275 | Two properties on carrer Josep Llimona | 2023-10-17 | 4 |
| 46636 | PAU 07 Les Carolines | 2023-06-20 | 2 |
| 46637 | Community equipment systems | 2021-02-03 | 5 |
| 46647 | Delimitation PAU-01 El Cònsol | 2020-03-11 | 2 |
| 46648 | Errors and dysfunctions | 2019-09-17 | 14 |
| 46649 | Can Puig soil classification | 2017-09-15 | 2 |
| 46650 | PAU 15 La Presentació | 2017-09-15 | 25 |
| 46651 | Equipment uses and material errors | 2024-03-14 | 6 |

Detail URLs are `https://arenysdemar.cat/fitxa.php?id=<ID>`; the exact fetched
URLs are also listed in `evidence/validation.json`. Each record retains its
municipal title, original description, municipal detail URL, inventory URL,
RPUC dossier link and ID, and every attached PDF with title and detail-page
provenance. Thumbnail links do not create duplicate documents. The municipal
page ID is a source identifier, not an invented expediente number. RPUC links
are references; the RPUC application and PDFs are not independently parsed.

## Date and coverage semantics

`fecha_publicacion` means the inventory's explicit **Publicat al DOGC el** label,
checked against the detail page, not page update, crawl or agreement time.
`fecha`, `fecha_acuerdo`, `fecha_aprob` and `fase` remain null. Original narratives
and document labels preserve the information needed for subsequent legal review;
this adapter does not infer a definitive phase or legal validity from publication.

Two notable source inconsistencies are preserved rather than corrected by guess:
page 46633 describes 2013-11-06 as plenary approval but labels its attachment CTUB
conformity; page 46650 labels publication 2017-09-15 while narrating definitive
approval 2017-09-28. Multiple procedural events occur in other narratives. None
are silently collapsed into one approval date. The general inventory also stops
at 2024 publications despite newer items elsewhere on the site.

No PDF map is converted to coordinates, and no municipal centroid or random
location substitutes for project geometry. Licence forms, applications and
procurement announcements do not become granted-licence or project records.

## Implementation and validation

The scraper uses the preinstalled requests/BeautifulSoup dependencies and the
existing AyuntamientoAdapter contract. It respects the site's declared
ISO-8859-1 encoding; evidence captures are decoded and saved as UTF-8. HTTP
requests have 40-second timeouts and a streamed 4 MB HTML limit; exceeding it
raises an error instead of truncating. All entries are fetched, without a
record limit. Pagination indicators cause an explicit error requiring crawler
review; there is no silent first-page-only success. Unexpected inventory items,
invalid dates, missing documents/dossiers, title mismatches or conflicting
publication labels also fail. Output replaces the previous snapshot atomically
only after all details succeed. Updates refresh this same full scoped snapshot;
no incremental state or historical completeness is claimed.

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_arenys_de_mar -v`: **7 tests passed**,
  covering date semantics, document grouping/provenance, duplicate entries,
  pagination rejection, invalid sources/content, failed snapshot preservation,
  disabled licences and manifest settings.
- Real `ArenysDeMarAyuntamientoAdapter.backfill_proyectos` run: **9 records**,
  **83 PDF links**, ten successful source requests (inventory plus nine details).
- `evidence/proyectos.jsonl`: actual live rows.
- `evidence/validation.json`: live count, source URLs, limitations and test result.
- `evidence/general-inventory.html` and `evidence/fitxa-*.html`: source captures
  made by the live adapter. Evidence remains local and is not source code.

Only the four requested source files were added; no shared sources, dependencies,
credentials, database, production or deployment tools are involved.
