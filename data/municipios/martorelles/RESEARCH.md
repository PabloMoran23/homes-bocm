# Martorelles — INE 08115, Barcelona

Live verification: 2026-11-09. This municipality is Martorelles, not Martorell
or Santa Maria de Martorelles. Adapter coverage is deliberately partial:
**9 records from 8 municipal detail pages**, with 14 retained document links.
No granted-licence inventory is claimed. Scheduling and coordinate jitter are
disabled; all records have `publication_ready: false`.

## Official inventory and extraction

The municipal inventory is
https://www.martorelles.cat/ajuntament/consistori/accio-i-pla-de-govern/plans-projectes-campanyes-programes
with pages `?pag=2` and `?pag=3`. All three were fetched live. It contains both
physical works and unrelated policy plans, grants and programmes. The adapter
reads the declared page count, follows pagination links, deduplicates detail
URLs, and refreshes the complete inventory on both backfill and update. Bounds
or changed markup cause failure before replacing output, never a partial write.

Supported titles are explicit `Projecte`, `Obres de millora`, `Substitució de
fusteria`, water-network/climate-control `Adequació de la`, and `Pla d'Ordenació
Urbanística Municipal`. Each requires a matching detail heading and municipal
PDF attachments in the actual content container. This is a conservative subset,
not a claim that all other catalogue items are irrelevant or that every future
matching title has been reviewed. Terse physical-work cards such as Barri antic,
Asfaltat del polígon and Clavegueram are currently outside this adapter's scope.
Policy plans, subsidies, procurement notices, news and application forms are not
converted into projects or granted licences.

The eight official detail pages, relative to that inventory URL, are:

- `/projecte-reforma-integral-de-la-cuina-i-lequipament-de-lescola-simeo-rabasa.html`
- `/pla-dordenacio-urbanistica-municipal-modificacio-puntual-.html`
- `/projecte-renovacio-vials-poligon-industrial-fase-1.html`
- `/obres-de-millora-a-lescola-bressol-municipal-els-cirerers.html`
- `/substitucio-de-fusteria-interior-a-lescola-simeo-rabasa.html`
- `/projecte-dobra-per-a-la-installacio-dun-bar-al-pati-del-poliesportiu-municipal.html`
- `/13683-adequacio-de-la-xarxa-dabastament-daigua-des-del-diposit-municipal.html`
- `/adequacio-de-la-climatitzacio-del-celler-de-carrenca.html`

These represent kitchen reform, Horta 5-7 zoning modification, industrial roads,
school exterior transformation and patio access, internal school doors, sports
facility bar, water network and climate control works. The school page describes
two separate works: exterior and patio documents are grouped into two records.
For each other instrument, all its attachments remain together in one record.
Stable IDs derive from the detail URL and, where needed, the school work label.
Every document retains its source detail URL. PDF filenames are not interpreted
as approval dates, expediente numbers or evidence of licence grants.

## Dates, provenance and limitations

`fecha_publicacion` comes from the catalogue's explicit dated entry. Detail-page
update timestamps are not project publication, agreement or approval dates.
The HTML does not establish exact agreement/approval dates consistently; those
fields and procedural phase remain null. A document label such as “Anunci” or
“Edicte” is retained as provenance, not a procurement award or a granted licence.
The zoning record is the published modification instrument, not an assertion
that the modification or the whole POUM is definitively approved.

PDF contents are not parsed. Live link checks found 13 PDF signatures and one
HTTP 404: the patio project's original `/media/repository/y/ajuntament/…` URL.
The patio announcement is available. The broken original link is retained and
reported; no replacement URL is guessed. Neither link checks nor attachment
labels establish a legal approval phase. Exact URLs and statuses are recorded
in local `evidence/document-checks.json` and `evidence/validation.json`.

No verified project geometry is available from this HTML source. Latitude,
longitude and geometry remain null; no municipality centroid, invented street
point or jitter is substituted. This is not full historical planning coverage,
and it does not discover other municipal registers or parse RPUC dossiers.

## Validation

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_martorelles -v`: 7 tests passed. Tests cover
  pagination, exclusions, date semantics, grouped documents, distinct school
  instruments, changed sources, complete update and preservation on failure.
- Direct live `MartorellesAyuntamientoAdapter.backfill_proyectos`: 9 records,
  3 inventory pages and 8 detail pages; output `evidence/proyectos.jsonl`.
- `evidence/validation.json`: live count, source URLs, document URLs, checks and
  coverage limitations. `evidence/captures/` holds the actual HTML fetched by
  the adapter (filenames are SHA-256 URL prefixes).

Evidence is local only. No dependencies, shared source files, database,
credentials, deployment, publishing or repository remote operations are needed.
