# Torroella de Montgrí — INE 17199, Girona

Verified on 2026-11-07 using anonymous official municipal sources. This adapter
provides a **partial current inventory snapshot**, not a complete municipal
history. Scheduling and licences are disabled. No coordinates are supplied and
`publication_ready` is false. The local evidence directory is `evidence/`.

## Official source discovery

- https://www.torroella-estartit.cat/ca/urbanisme-planejament-i-gestio-urbanistica.html
  — municipal Territori i Sostenibilitat landing page. Links to current planning,
  in-process planning/management/execution, and urban agreements. The department's
  functions and licence procedures are not granted-licence records.
- https://www.torroella-estartit.cat/ca/planejament-urbanistic-vigent.html
  — current-planning index: consolidated PGMO, general-plan modifications and
  derived planning/RPUC links. Discovered and captured, not extracted by this
  adapter. Regional plans and generic category links are not individual projects.
- https://www.torroella-estartit.cat/ca/planejament-derivat.html
  — separate derived-planning inventory with instrument/document links.
  Discovered and captured, outside the implemented snapshot.
- https://www.torroella-estartit.cat/ca/planejament-gestio-i-execucio-urbanistica-en-.html
  — implemented source. The municipality explicitly describes documents,
  public-information notices and agreements for instruments in process.
  HTTP 200; a single HTML document, with no pagination in the reviewed content.
  The adapter raises on detected pagination instead of silently limiting results.

`evidence/discovery.json` retains discovered links and capture names for the first
three sources. `inventory.html` is the initial discovery capture;
`live-inventory.html` is the response used by the final adapter extraction.

## Implemented coverage and grouping

Every instrument block in sections **2.2** and **2.3** is parsed. The current live
result has four records, with six document references:

1. Projecte urbanització polígon 1 zona Creu de la Rutlla, **135007K**:
   initial-approval BOP notice and municipal drive project link, one instrument.
2. Estudi de Detall de la parcel·la 4 del conjunt Sol Ric, urbanització Torre Vella:
   definitive-approval certificate and consolidated study, one instrument.
3. Pla de millora urbana, carrer Alfons Mercader / carrer Montpeller, **195X**:
   initial-approval decree. The decree actually reiterates the initial approval;
   the adapter's phase reflects the municipal inventory wording, not a claim
   that this is a new project or definitive approval.
4. Modificació puntual del PGMO, càmping de les Medes, **115629X**:
   initial-approval project document. Although the municipality puts it in its
   management/execution section, its type is planning, not a construction licence.

Attachments remain grouped under `documentos` with original labels, absolute URLs,
and the inventory URL as provenance. Municipal drive share URLs are retained;
the adapter does not fetch their contents or claim that downloads are available.
Dates in filenames are not parsed. IDs use the published expediente when present;
otherwise the normalized instrument title with its approval prefix removed.
Duplicate identities fail for review rather than being merged speculatively.

Section **2.1** is deliberately outside coverage. It contains general-plan and
other instruments with separate title/document blocks and overlapping Tamariu /
UA1M Cala Montgó presentations. Manual inspection of its initial notice and
provisional project confirmed multiple stages of the Carrer Tamariu instrument;
they must not become two projects. This adapter makes no completeness claim for
that section. The PLATER regional consultation and municipal objections under
“ALTRES DOCUMENTS DE CONSULTA” are also excluded.

The parser requires the official heading, content container and ordered section
markers. Unknown instrument layouts, unsupported document hosts/paths, missing
sections and pagination raise errors. There is no fixed record-count limit or
first-N truncation. Updates refresh the complete supported snapshot; disappearing
items do not mean cancellation, and no incremental-history state is claimed.

## Date semantics and geometry

The HTML inventory does not provide explicit publication or agreement dates for
these four instruments. `fecha`, `fecha_publicacion`, `fecha_acuerdo` and
`fecha_aprob` are therefore null. No crawl time, filename date, signature date or
historical date quoted inside a document becomes an instrument date.

Manual PDF checks demonstrate why this matters: the Creu de la Rutlla notice
states an initial approval decree of **2026-01-26**, while its BOP header is
**2026-03-12**. The PMU decree of **2026-08-18** reiterates an earlier initial
approval and describes an intervening provisional approval and return by CTUG.
These are documentary observations, not dates extracted by the HTML adapter.
Selected PDF captures and their source URLs are mapped in
`evidence/document-captures.json`; available pdftotext outputs are local research
aids, not adapter dependencies.

No project geometry is verified. `lat`, `lon` and `geometry` are null, with no
municipal centroid or jitter substituted. The inventory has not been verified as
a granted-licence register; licence forms, procurement and general news are not
used as records.

## Validation and reproduction

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_torroella_de_montgri -v`: **4 tests passed**.
  Reduced offline HTML fixtures exercise grouping, dates remaining unknown,
  type/phase separation, stable identity, schema loss, pagination, foreign links,
  duplicated instruments and disabled licences without HTTP.
- Direct live `TorroellaDeMontgriAyuntamientoAdapter.backfill_proyectos` after
  tests: **4 genuine records**, **6 document links**.
- `evidence/proyectos.jsonl`: actual adapter output.
- `evidence/validation.json`: live count, source URLs, test result and limitations.

For another live run, instantiate the class with slug `torroella-de-montgri` and
optional config `{"evidence_dir": "evidence"}`, then call
`backfill_proyectos(Path("evidence/proyectos.jsonl"))`. No credentials, database,
publishing, dependency installation or shared-code changes are needed.
