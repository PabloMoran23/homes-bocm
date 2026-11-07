# Cubelles — INE 08074, Barcelona

Verified 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One adapter, deliberately partial coverage of the current municipal Projectes
inventory. Two real projects, three grouped document links. Scheduling and
licence extraction are disabled; no geometry or coordinates are inferred.

## Discovery and official sources

- https://www.cubelles.cat/ajuntament/urbanisme — HTTP 200; official municipal
  Urbanisme index links to Projectes, the transparency planning page and RPUC.
- https://www.cubelles.cat/ajuntament/urbanisme/projectes — HTTP 200; dated
  inventory with two entries, both fetched. The two `.pager` containers are
  empty in the captured response: there are no additional linked pages today.
- https://www.cubelles.cat/ajuntament/urbanisme/projectes/projecte-constructiu-renovacio-aigua-potable.html
  — HTTP 200. Named construction project for water supply renewal in
  Esparraguera, Farigola, Goya, Joan Miró, Picasso amb Greco, Ribera and Velázquez.
  Publication date displayed in the inventory: 2026-09-14. Contains a technical
  project PDF and a BOPB notice; these are documents of one project, not two
  project records. No phase or agreement date is extracted from the title or
  announcement label.
- https://www.cubelles.cat/ajuntament/urbanisme/projectes/projecte-urbanitzacio-antiga-central-termica-cubelles.html
  — HTTP 200. Named urbanization project for the former thermal power station.
  Publication date displayed in the inventory: 2025-10-28. The body explicitly
  says public information following initial approval. One technical PDF.
  The record's phase reflects that published statement, not a claim about the
  latest legal state of the project. The date of approval is not stated in the
  HTML and remains null. The page update date (2026-09-14) is not an approval.
- https://seu-e.cat/ca/web/cubelles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200, reached through the municipal site's planning redirect. It provides
  external RPUC and MUC links rather than individual planning records. The RPUC
  link contains `municipiSel=08074`, corroborating municipal identity. This
  adapter does not claim to scrape those regional inventories.
- https://seu-e.cat/es/web/cubelles/tramits-i-gestions/-/tramits/classificacio/urbanisme
  — discovered in official search results as a list of application procedures
  (licences, certificates and extensions). Not a granted-licence register and
  not used as project data. No public granted-licence inventory was verified.

The PDF URLs retained in `documentos` are:

- https://www.cubelles.cat/media/repository/Urbanisme/Projecte_renovacio_aigua_potable/Projecte.pdf
- https://www.cubelles.cat/media/repository/Urbanisme/Projecte_renovacio_aigua_potable/Anunci_BOPB.pdf
- https://www.cubelles.cat/media/repository/Urbanisme/250602_PU_CT_Cubelles_s.pdf

All three returned HTTP 200 and `application/pdf` to live HEAD requests. Full
PDF contents were not downloaded or parsed (the inventory advertises technical
files of 34.7 MB and 210.6 MB). Document labels, publisher where displayed and
source detail URL are retained. An announcement is supporting documentation,
never a separate project or proof of a granted licence.

## Extraction contract and limits

The adapter fetches the fixed official inventory, follows all links in its
pagination controls and fetches every listed project detail. Repeated URLs
across pages are deduplicated; conflicting titles/dates fail. Pagination loops
are visited once. Unsupported controls, external destinations and more than
100 inventory pages cause an error before output is written; the adapter never
returns a silently truncated snapshot. HTML downloads are bounded at 4 MB with
45-second request timeouts. Redirects, missing inventory/detail structure,
unreviewed entry types and missing technical project documents fail closed.

IDs derive from actual detail URLs; all documents within each detail page are
grouped under that instrument, deduplicated by URL. Updates refresh the complete
inventory snapshot and do not infer deletions or an incremental date cursor.
The `fecha_publicacion` field comes only from the dated inventory entry, with
its URL recorded separately. Generic `fecha`, `fecha_acuerdo` and `fecha_aprob`
remain null. Descriptions retain their original source semantics. Only the
explicit initial-approval narrative determines `fase`; project type does not.

This is not a full historical works, planning or urban-management inventory.
Other projects may exist in municipal topic pages, regional registers or
archives outside Projectes. PDFs may contain additional dates, identifiers or
geometries that this HTML adapter does not extract. No project location has
been verified: `lat`, `lon`, `geometry` are null and `publication_ready=false`.
No centroid, parcel or random jitter is substituted. `schedule.enabled=false`,
`geocode.jitter_missing=false`, `licencias.enabled=false`.

## Validation and local evidence

- `python -m unittest municipio.test_cubelles -v`: 7 passed. Exercises publication
  versus agreement dates, missing metadata, grouped/deduplicated documents,
  rejection of forms/news/notice-only details, multiple inventory pages,
  external/unsupported pagination, unchanged previous output on parse failure,
  manifest loading and disabled licences.
- Direct live `CubellesAyuntamientoAdapter.backfill_proyectos`:
  `status=ok`, `rows=2`; no mocked network or fixture-derived live records.
- `evidence/proyectos.jsonl`: the two actual extracted records.
- `evidence/validation.json`: live record count, extraction source URLs,
  document URLs, checked timestamp and explicit limitations.
- `evidence/*.html`: discovery and extraction captures. Adapter capture names
  use the first 16 hexadecimal characters of SHA-256 of their source URL.
- `evidence/document_checks.json`: live PDF HEAD results.

Evidence is local, outside the four source deliverables. No shared source or
dependency files were changed; no publishing or database operation was used.
