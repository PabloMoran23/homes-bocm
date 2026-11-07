# Cunit — INE 43051, Tarragona, Catalunya

Verified live on 2026-11-07. One adapter covers the municipal **Planejament**
inventory as currently published. This is partial municipal coverage, not a claim
that every instrument in it remains legally current. Scheduling, granted-licence
extraction and coordinate jitter are disabled. Records have no verified geometry
and explicitly set `publication_ready: false`.

## Official sources discovered

- https://www.cunit.cat/informacio-i-serveis/urbanisme-i-obres/planejament-urbanisme/
  — HTTP 200 with a browser User-Agent. Primary extraction inventory: two tables,
  3 notices marked “En tràmit” and 11 marked “Tancat”. Each row links to a
  `/planejament/` detail page. Headers explicitly distinguish initial and definitive
  approval dates. Both Toolset views have `type=disabled`, `max_pages=0`: the
  published inventory has no pagination. The adapter rejects pagination metadata
  or next-page controls rather than silently taking a first page.
- All 13 included detail URLs are listed in local `evidence/validation.json`.
  These are fetched live by the adapter, not assembled from search snippets.
  Each has municipal planning markup and documentary references.
- https://www.cunit.cat/informacio-i-serveis/urbanisme-i-obres/obres/
  — HTTP 200; licence application/service information, not a granted-licence
  register. Excluded from extraction.
- https://www.cunit.cat/informacio-i-serveis/urbanisme-i-obres/planejament-en-tramit-2/
  — HTTP 200; older narrative inventory including 2007–2017 instruments, links
  to `old.cunit.cat`, and some duplicates of the chosen inventory. Discovered and
  captured, but not merged into this bounded adapter's coverage. Its title does
  not establish that all its historical entries are still in process.
- https://www.cunit.cat/informacio-i-serveis/urbanisme-i-obres/projectes-de-parcellacio-i-reparcellacio/
  — HTTP 200; separate historical management page, including La Pleta voluntary
  reparcelling and compensation-board statutes. Not covered by this adapter.
  Several certificate links on this page have malformed hostnames.
- https://www.cunit.cat/informacio-i-serveis/urbanisme-i-obres/pla-dordenacio-urbanistica-municipal/
  — HTTP 200; historical base POUM narrative (2006 approvals, 2007 DOGC
  publication), generic RPUC search and municipal viewer links. Discovered but
  outside this inventory snapshot; not emitted as an extra plan.
- https://mapes.cunit.cat/geoportal — HTTP 200 application shell. No feature
  geometry has been linked and verified against extracted instruments.
- https://www.cunit.cat/wp-json/wp/v2/pages?slug=planejament-urbanisme
  — HTTP 200 public WordPress page representation, inspected during discovery.
  Actual extraction uses the rendered tables and detail pages, not page metadata.

## Included and excluded records

The live extraction yields **12 instruments/projects from 13 included fiches**:
POUM amendments 4–7, SUD5 Miramar partial plan, proposed consolidated urban fabric
(TUC), FTTH network expansion plan, the Cunit-Nord regulating-reservoir specific
project BP24P, PA-16 Avi Pau reparcelling, SUD2 urbanisation project, SUD2 partial
plan, and the volume-ordering PMU for the Barcelona/Castell/Cèsar August/Rambla
del Prat block.

The initial and definitive SUD2 partial-plan notices have the same instrument,
initial approval 2019-07-30 and definitive approval 2020-04-30. They become one
record, retaining both fiches and their documents. This does **not** merge the
separate SUD2 urbanisation project or POUM amendment 5. The other excluded row,
“Cessió finca per construcció Institut”, is a land-transfer procedure mentioning a
future institute, not itself a construction project. No procurement announcement,
unrelated news or application form is used as a project or granted licence.

## Date semantics and provenance

`fecha_aprob_inicial` and `fecha_aprob_definitiva` come from their explicitly
labelled table columns. `fecha_aprob` is the definitive date when provided,
otherwise the initial date. `fase` follows that evidence; “Tancat” alone never
means definitive approval. The reservoir fiche links a definitive-approval PDF
but has no definitive date in the inventory: the adapter conservatively retains
the dated initial phase and the PDF link without inventing an approval date.
Source status, title and detail narrative remain in `fuentes`.

`fecha` and normalized `fecha_publicacion` remain null. Public-exposure dates
are preserved separately as `exposicion_publica_texto`; explicit publication
paragraphs remain in `publicaciones_texto`, per source fiche. The full source
narrative is also retained. These paragraphs can concern different phases, so
there is no single publication date inferred for the combined instrument.
For example, urbanisation SUD2 has initial approval 2020-07-21, definitive
approval 2022-07-19, and a narrative definitive BOP publication of 2022-10-18.
The source for amendment 7 inconsistently shows exposure on 2021-01-04 but
publication text saying 2020-01-04. Neither value is silently corrected or
substituted for an agreement date. URL upload dates and crawl time are never
used as approval/publication dates.

All document URLs retain their source fiche via `url_origen` and `urls_origen`.
The 75 unique links within records include technical PDFs, certificates, gazette
references and a source-linked public SharePoint project. FTTH's project PDF is
printed as a plain URL; it is retained too. Linked files are **not** individually
downloaded or certified accessible. HTTP links and malformed municipal URLs
(e.g. the duplicated host/path in amendment 5's provisional document) remain
as published rather than being guessed or silently repaired. Search/navigation
links outside dossier content do not become records.

## Implementation and validation

Requests have a 40-second timeout and a 4 MB response limit. Missing tables,
changed date-column schema, missing planning detail markup/documents, pagination,
invalid dates, conflicting grouped approval dates and off-site detail redirects
raise errors before replacing the output. IDs derive from stable municipal detail
slugs; the two explicitly matched SUD2 notices share one instrument key. Updates
refresh the complete covered inventory without a date watermark. Licence methods
write no records and report disabled.

Executed with the preinstalled runtime:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_cunit
```

Six tests passed: grouping and provenance; approval/publication separation;
closed status without definitive date; pagination and changed-source rejection;
land-transfer/form exclusion and invalid dates; conflicting approval rejection;
manifest and full-snapshot update behavior (several assertions per test).

A real `CunitAyuntamientoAdapter.backfill_proyectos` run returned 12 records,
75 documentary links, 12 unique IDs and no invented coordinates. An initial
request without a browser User-Agent returned 403, and a descriptive custom
User-Agent later disconnected; extraction succeeded with `Mozilla/5.0`.
Local evidence is in `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/captures/` (all 14 responses fetched by the adapter, mapped to source
URLs in validation), and discovery captures in `evidence/`. Evidence is local and
not part of the four source files. No shared files or dependencies were changed.
