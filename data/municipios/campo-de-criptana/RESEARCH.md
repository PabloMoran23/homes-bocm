# Campo de Criptana — Ciudad Real — INE 13028

Verified live on 2026-11-07. This adapter extracts a **partial current municipal
planning-document inventory**, not a historical register, granted licences or a
public-works execution register. It does not certify that every listed instrument
is legally in force. Schedule and licence extraction are disabled; missing
coordinates are never jittered. All records have `publication_ready: false`.

## Official inventory and extracted dossiers

The municipal [Obras públicas y Urbanismo index](https://transparencia.campodecriptana.es/obras-publicas-y-urbanismo/)
links the four supported detail pages below. All five pages returned HTTP 200 in
the live adapter run. The index discovers detail URLs rather than embedding six
fixed records in code.

- [Texto Refundido Plan de Ordenación Municipal](https://transparencia.campodecriptana.es/texto-refundido-plan-de-ordenacion-municipal/):
  one instrument, 35 document links: TRPOM 2022 secretarial diligence, urbanistic
  rules and rural/urban plans. These are components of one instrument.
- [Plan Parcial de Mejora «Polígono Industrial para Usos Agrícolas»](https://transparencia.campodecriptana.es/plan-parcial-de-mejora-poligono-industrial-para-usos-agricolas/):
  three distinct instruments identified by the page's left-column labels:
  original plan labelled 2007 (3 documents), amendment on minimum parcel
  conditions labelled 2012 (1 document), and compatible uses/extension amendment
  labelled 2024 (5 documents). Blank left-column rows continue the preceding
  instrument. The 2012 label and document filename ending in 2011 are retained
  as published, without inventing a date to resolve their difference.
- [Modificación Puntual 9/2018 «Travesía de la Mota»](https://transparencia.campodecriptana.es/modificacion-puntual-9-2018-travesia-de-la-mota/):
  one instrument, 3 documents: technical amendment, BOP rules announcement and
  DOCM announcement concerning definitive approval. Announcements are supporting
  documents, not extra projects or evidence of execution.
- [Modificación Puntual Nº 2/2025 «Ficha A-16 del Título VIII»](https://transparencia.campodecriptana.es/modificacion-puntual-no-2-2025-ficha-a-16-del-titulo-viii/):
  one instrument, 2 documents: technical amendment and BOP agreement announcement.

Every `documentos` entry retains the link label, document URL, row context and
municipal detail `source_url`. The record retains both its detail URL and index
URL. Document labels and URLs are transcribed from HTML; PDF contents are not
parsed or asserted. Approval, agreement and publication dates, and legal phase,
remain null. An instrument's year/number, upload directory, section update or
portal update is never used as an approval or publication date. PDF maps are not
converted to fabricated point coordinates or geometry.

## Other inventory branches and limits

The same official index currently also links:

- [Modificaciones puntuales en tramitación del TRPOM](https://transparencia.campodecriptana.es/obras-publicas-y-urbanismo/modificaciones-del-pgou/):
  mixed announcement/news listing, including a named amendment 12/2018 and a
  link hosted on another municipality's transparency domain. Not included in
  this adapter's supported technical-dossier pages; no complete pending-amendment
  coverage is claimed. Its HTML is captured locally.
- [Programas de Actuación Urbanizadora](https://transparencia.campodecriptana.es/obras-publicas-y-urbanismo/programas-de-actuacion-urbanizadora/):
  fetched HTML contains a heading and update notice, no named dossier documents.
  No PAU records emitted.
- [Datos de licencias](https://transparencia.campodecriptana.es/obras-publicas-y-urbanismo/datos-de-licencias/):
  HTML links a generic `Licencias.pdf` under a 2019 upload path. This has not been
  established as a record-level register of granted licences; excluded. Licence
  extraction remains disabled, regardless of the page label.
- “Proyectos y pliegos licitación de las obras públicas” links to the state
  procurement portal. Procurement notices are excluded and are not counted as
  physical projects, granted licences or evidence of completed works.

The selected index and dossier pages expose their document lists directly in
HTML, without observed pagination. All links in the selected detail content are
processed, with no page or record cap. If standard pagination/next/load-more
controls appear, extraction raises instead of silently truncating. Missing
content, unknown grouping, ungrouped PDF links, external document domains and
unexpected redirects also raise before overwriting the output snapshot. Update
refreshes the entire supported snapshot; it does not claim incremental historical
coverage or silently skip failed detail pages.

## Validation and reproducibility

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
No packages installed or dependencies changed.

- `python -m unittest municipio.test_campo_de_criptana -v`: **7 passed**.
  Tests cover document continuation/grouping and separate amendments, dates and
  geometry left unknown, alternate heading levels, exclusion of navigation and
  forms, detail discovery scope, pagination and foreign-document rejection,
  preserving an existing snapshot on fetch failure, manifest loading and disabled
  licences without a network request.
- Real live extraction through `load_manifest('campo-de-criptana')`,
  `load_portal_adapter(...)`, and `adapter.backfill_proyectos(...)`: **6 records,
  49 document links**. Manifest adapter import and shared entity annotation ran
  successfully; the classifier reports all six entity categories unknown. No
  residential/industrial entity category is inferred to bypass that result.
- Local `evidence/proyectos.jsonl` holds actual records. `evidence/validation.json`
  includes `live_records`, source URLs, extraction timestamp, document counts,
  limitations and test results. `evidence/live/` contains the exact five HTML
  responses consumed by the adapter, named by the first 16 hexadecimal characters
  of SHA-256(source URL). Additional descriptive HTML captures of the other
  investigated municipal branches are under `evidence/`.

Only the four requested source files are added. Evidence is local, not committed.
No deployment, publishing, external writes or database actions were performed.
