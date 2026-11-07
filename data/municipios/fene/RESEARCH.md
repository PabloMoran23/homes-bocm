# Fene — INE 15035, A Coruña, Galicia

Verified live on 2026-11-07. This adapter extracts the municipal PXOM document
inventory as **one planning instrument with 19 attached document links**, not 19
projects. Coverage is deliberately partial. `publication_ready` is false, licences
and scheduling are disabled, and missing geometry is never replaced with jitter
or a municipal centroid.

## Official sources discovered

- https://www.fene.gal/portal-cidadan/presentacion-urbanismo/gl — HTTP 200;
  municipal explanation of the urban-planning service, linking its PXOM and
  cartography. Explanatory text is not a project or granted licence.
- https://www.fene.gal/portal-cidadan/urbanismo/gl — HTTP 200; current municipal
  service index. It links the PXOM, a rural-settlement modification for Os Buios,
  O Redondo, O Feal, Lubian and O Piñeiro, the Camiño Regueiro detail study,
  a Xunta register entry labelled Revisión do PXOM, the fire-prevention plan and
  EEI Magalofes equipment change. Those other instruments are outside this
  adapter's PXOM-document snapshot; their destination contents were not used as
  extracted records. The banner index is not represented as complete municipal
  coverage.
- https://www.fene.gal/portal-cidadan/pxom/gl — HTTP 200; extraction source.
  Nineteen named PDF/ZIP entries: memory and annexes, five books of urban rules,
  APE text/PDF/map packages, equipment and exceptional-use fiches, protected
  assets catalogue and graphics, rural-environment study and financial/action
  programme. All are retained under one stable `fene-pxom` identity.
- https://www.fene.gal/portal-cidadan/cartografia-pxom/gl — HTTP 200; legacy Flash
  object referencing `/flash/datos_pxom.xml`. No verified feature geometry was
  obtained or inferred. The XML and Flash contents were not extracted.
- https://www.fene.gal/portal-cidadan/xestions-municipais-urbanismo/gl — HTTP 200;
  procedures such as tax declarations and bank guarantees, not a licence register.
- Municipal news search also surfaced
  https://www.fene.gal/portal-cidadan/noticia/gl/8969 and
  https://www.fene.gal/portal-cidadan/noticia/gl/9174 about contracting the PXOM
  revision. These are discovery context only, not approved-plan records or
  licence grants, and supply no dates to the extracted record.

## Extraction, provenance and limitations

The parser requires the specific PXOM heading and named document entries in the
main content, including memory, urban rules and financial-study documents.
Navigation-only, login-like or structurally changed responses fail rather than
produce a placeholder. Every document heading is inspected; unexpected document
URLs fail the extraction. Relative paths are resolved, original hrefs and labels
are retained with their inventory provenance, and duplicate targets are grouped.
There is no row or document slicing.

The reviewed page has empty pager divs and no continuation. Nonempty pagination,
next links and load-more controls raise an explicit error requiring traversal
review. Updates replace the complete current snapshot; they do not append events
or advance a cursor. HTTP requests have timeouts, a 3 MB response bound and checks
for unexpected redirects/content types. The live page declares ISO-8859-1 through
HTML metadata; parsing preserves its Galician labels.

No approval, agreement or publication date is stated in this inventory.
`fecha`, `fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` remain null; neither
filename years nor HTTP/crawl dates are promoted to legal dates. `fase` remains
null. The source identifies a real planning instrument but this adapter does not
certify the legal currency of every document or parse the attached PDF/ZIP
contents. No parcel coordinates, geocoding or inferred locations are emitted.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_fene -v`: **7 tests passed**, including grouping,
  provenance, missing date/geometry semantics, Latin-1 decoding, duplicate targets,
  inventories over 50 documents, pagination rejection, changed/missing content,
  manifest loading, disabled licences and snapshot updates.
- Live extraction through `load_portal_adapter(load_manifest('fene'))` and
  `backfill_proyectos`: **1 actual record, 19 documents**. The shared registry's
  entity annotation reports an unknown entity classification; this is not a
  publication approval.
- All 19 linked documents were checked with streamed GETs: HTTP 200 and PDF/ZIP
  file signatures. This checks availability/format, not document contents.
- Local `evidence/proyectos.jsonl` contains the live record;
  `evidence/validation.json` includes record count, source URLs, limitations,
  parser-test result and document checks. `evidence/document_checks.json` retains
  HTTP and format observations. HTML captures cover all five directly inspected
  municipal pages; `evidence/indicedelamemoria.pdf` is a small genuine sample.
  The extraction capture `pxom.html` retains the original response bytes.

Only the four requested source files were added. Evidence remains local and is
not intended for commit. No shared code, dependencies, credentials, deployment
systems or git metadata were modified.
