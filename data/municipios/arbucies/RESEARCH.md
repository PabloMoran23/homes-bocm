# Arbúcies — Girona — INE 17009

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter extracts a partial snapshot of physical public works from the
municipality's own service inventory. It does not cover every municipal project,
planning instrument or granted licence. Scheduling, missing-coordinate jitter
and licence extraction are disabled. `publication_ready` is false.

## Discovery and official sources

- Municipal urbanism department:
  https://www.arbucies.cat/ca/arees-i-regidories/urbanisme-territori-i-activitats.html
  — HTTP 200, links to the works inventory, planning service, licence service and
  a separate works-news category. Captured as `evidence/inventory-2.html`.
- **Extracted inventory**:
  https://www.arbucies.cat/ca/arees-i-regidories/urbanisme-territori-i-activitats/obres-i-infraestructures-municipals.html
  — HTTP 200. Four titled physical interventions with explicit municipal
  execution narratives. Not a procurement feed or an application-form listing.
  Captured during discovery as `works.html`, and by the live adapter as
  `live-works.html`, both under `evidence/`.
- Planning service:
  https://www.arbucies.cat/ca/arees-i-regidories/urbanisme-territori-i-activitats/planejament-urbanistic.html
  — HTTP 200, its VIGENT section refers to
  https://dtes.gencat.cat/rpucportal/#/consulta/cerca and EN TRÀMIT has no instrument
  documents in the response. This generic register-search link is not an
  individual planning record. `evidence/inventory-0.html`.
- Featured urbanism inventory:
  https://www.arbucies.cat/ca/destacats/obres.html
  — HTTP 200, one Mirador planning highlight; `evidence/inventory-1.html`.
  Its detail at
  https://www.arbucies.cat/ca/destacats/obres/pla-parcial-dordenacio-mirador-darbucies.html
  (HTTP 200, `evidence/mirador.html`) shows a publication date of 2023-10-11 and
  refers back to the planning service. No technical documents are exposed there.
  Not included in this physical-works adapter. Neither the highlight's date nor
  its initial-approval wording is used as a definitive approval date.
- Search discovery also identified the official transparency planning entry
  https://seu-e.cat/es/web/arbucies/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  referring to RPUC/MUC, and municipal forms at
  https://www.arbucies.cat/ca/tramits-presencials.html . Neither is used to claim
  individual instruments or granted licences. Search snippets are discovery
  evidence only; emitted records come from the adapter's live HTTP response.

## Actual coverage and semantics

The four works are:

1. Adequació i millora del Museu Etnològic del Montseny La Gabella, fase 3.
2. Arranjament danys provocats per la Borrasca Jana entre els dies 7 i 9 de març de 2025.
3. Renovació del sistema de climatització del Centre d’Arts Escèniques Naus Ayats.
4. Instal·lació de sistemes de calor amb biomassa i xarxes de calor municipal
   (the description specifies extension to the municipal nursery El Jardinet).

The municipality describes museum and HVAC works as being executed, and the
storm repairs and heat-network extension as having been carried out. These are
undated source assertions, not independently verified progress as of crawl time.
No publication, agreement or approval date is supplied for these sections;
`fecha`, `fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` remain null.
The storm dates are event dates. Grant identifiers 2025/6666, 2025/5587 and
CLT213/25/000001 stay in the verbatim descriptions; they are not municipal works
expediente identifiers. No dates are inferred from them.

One record groups each heading and all its following narrative blocks, until the
next heading. The organisational heading “Àrea de territori i sostenibilitat/Medi
Ambient” is excluded. Stable IDs hash normalized section titles, not crawl order;
a future title change will require identity review. Record provenance retains
the inventory URL and exact section heading. Links within each work are retained
and deduplicated in `documentos`. The live page has no technical attachments:
its images are funding logos and are excluded, so `documentos` is currently empty.
The municipal HTML itself is the documentary source; no technical dossier is
claimed. No coordinates, municipal centroid or geometry are fabricated.

## Extraction and validation

The complete service page is fetched with a 30-second timeout and a 2 MB bound.
There is no pagination on the observed inventory. Pagination controls or next
links cause a clear failure, rather than silently limiting the result. Missing
inventory structure, duplicate headings, an empty inventory, or sections without
explicit physical-work execution evidence also fail. There is no item cap.
Update refreshes the entire snapshot without an inferred date watermark.

- `python -m unittest municipio.test_arbucies -v`: six tests passed with the runtime
  above. Coverage includes document grouping/deduplication, date semantics,
  provenance, execution states, administrative dividers, stable identity,
  rejection of forms/procurement-only text, changed/empty content, duplicate
  headings, pagination rejection, manifest loading, disabled licences and refresh.
  The optional local-capture test also passed against the discovered HTML.
- Live extraction through `load_portal_adapter(load_manifest('arbucies'))` and
  `backfill_proyectos`: four genuine records, four unique IDs. Shared entity
  policy annotated all four as unknown category (status ok); no category is
  fabricated to bypass this limitation.
- `evidence/proyectos.jsonl`: actual live adapter output.
- `evidence/validation.json`: timestamp, `live_records: 4`, source URLs, test
  result, limitations and adapter/policy result. Evidence remains local.

Only the four requested source files were added. No shared modules, dependencies,
credentials, database, deployment or publishing tools were used or modified.
