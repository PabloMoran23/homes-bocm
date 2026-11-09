# Guissona — INE 25110, Lleida

Verified live on 2026-11-08 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter provides a **partial snapshot of two official inventories**, with
seven genuine planning instruments / works projects. It does not claim full
municipal coverage, a granted-licence register, or readiness for map publication.

## Official source discovery

1. Municipal urbanism index:
   https://www.guissona.cat/serveis-de-guissona/urbanisme/
   and management inventory:
   https://www.guissona.cat/serveis-de-guissona/urbanisme/gestio-urbanistica
   Both returned HTTP 403 to direct live requests. The planning path
   https://www.guissona.cat/serveis-de-guissona/urbanisme/planejament-urbanistic
   also returned 403. Search indexing exposed management project names, but
   indexed snippets are not used to generate records. Responses saved locally
   as `evidence/source-0.html` through `source-2.html`.
2. Official municipal transparency seat, **Planejament urbanístic**:
   https://seu-e.cat/ca/web/guissona/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
   HTTP 200, three static linked entries under PLANS URBANÍSTICS:
   Pla Parcial SUD-1, Pla Parcial SUD-8 and Pla residencial SUD-7.
   Their document/file/folder links are Google Drive URLs published by the
   municipality itself; the adapter retains that provenance. They are not
   independently authenticated documents or evidence of definitive approval.
   The displayed 22/08/2019 update belongs to the web content, not the plans.
3. Official **Projectes i documents tècnics en exposició pública**:
   https://seu-e.cat/ca/web/guissona/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-i-documents-tecnics-en-exposicio-publica-211
   HTTP 200, four static document-bearing entries: photovoltaic installations
   at four named municipal buildings; initial modification 10 of the POUM;
   provisional modification 12 of the POUM; and sanitation-system improvements.
   Modification 10's title continues in a separate municipal-page link within
   the same paragraph; this is retained as one title and one instrument.
   The sanitation PDF was downloaded anonymously, HTTP 200 application/pdf,
   524900 bytes, and saved as `evidence/sanejament.pdf` from:
   https://seu-e.cat/documents/4027575/20695976/MILLORES+EDAR+GUISSONA_Censurat.pdf/a8e62fb5-c1d5-40a8-8f50-785d9481a22f
4. Additional official **Normativa d'urbanisme** inventory, inspected HTTP 200:
   https://seu-e.cat/ca/web/guissona/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
   Contains one tabular PAU-7 recast urbanization project (publication-date cell
   blank) and legacy management content last updated in 2019. Not extracted by
   this adapter: table-based and legacy management inventories remain outside
   its declared two-inventory scope. Some legacy Drive folders are reused for
   different named instruments; they are not assumed to be unique expediente
   identifiers. Capture: `evidence/normativa-d-urbanisme.html`.

## Extraction contract and limits

The manifest uses the exact municipality/province and INE, dynamic adapter import
contract, `proyectos.source: ayuntamiento`, `schedule.enabled: false`,
`licencias.enabled: false`, and `geocode.jitter_missing: false`. No shared code
or dependencies are changed.

Each run refreshes both static inventories completely. There is no date cutoff,
record limit or silent first-page truncation. New active pagination or tabular
content causes an explicit error requiring crawler review. HTTP failures, empty
inventories, missing planning headings, unknown document-bearing entry types and
unexpected redirects also fail. Both inventories must parse before output is
replaced, preserving an existing snapshot on a failed refresh. Requests have
40-second timeouts and a 4 MB per-response bound.

Extraction is scoped to actual journal content paragraphs, excluding navigation,
service descriptions and indicator metadata. An instrument receives all supported
Drive/seat document links in its paragraph in `documentos`, each with its source
page; duplicate paragraphs merge document links. Source listing URLs and primary
document links are retained. Filenames, upload-like numbers and crawl dates are
never converted to approval dates. Known initial/provisional phases are parsed
from explicit title wording, not inferred from document type. Generic `fecha`,
`fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` remain null.

The exposure page's continued listing does not establish that a consultation is
still open today. The adapter does not recurse into Drive folders, parse linked
PDF contents, or resolve all documents in RPUC. It provides the municipality's
published project references, not complete dossier contents. No procurement
announcement, licence application form or unrelated news is emitted. No geometry
is verified; `lat`, `lon` and `geometry` remain null and `publication_ready` false.
The shared entity-policy annotator currently classifies all seven records as
unknown; this does not supply publication eligibility.

## Validation and local evidence

- `.../venv/bin/python -m unittest municipio.test_guissona -v`: **8 passed**.
  Tests cover date semantics, phases, split titles, multiple document grouping,
  duplicate paragraphs, non-record rejection, navigation exclusion, pagination
  and markup-change rejection, failure preserving old output, manifest resolution
  and disabled licences.
- Real live extraction through `load_manifest`, `load_portal_adapter` and
  `backfill_proyectos`: **7 records**, shared entity-policy status `ok`.
- `evidence/proyectos.jsonl`: actual extracted records (including policy annotation).
- `evidence/validation.json`: live count, timestamp, source URLs and limitations.
- `evidence/planejament.html` and `evidence/exposicio.html`: exact live extraction
  source captures. Discovery captures and the sanitation PDF are also local.
- Evidence is local only. No credentials, external writes, deployment, database,
  installation, push, PR or publishing operations were used.
