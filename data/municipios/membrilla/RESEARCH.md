# Membrilla — INE 13054, Ciudad Real

Verified on 2026-11-09 using the preinstalled Python runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter covers the current municipal planning-document inventory, not the
whole municipality's historical projects, granted licences or completed works.
Scheduling, missing-coordinate jitter and licences are disabled.

## Official inventory and provenance

https://membrilla.es/planeamiento-urbanistico/ is the town council's current
planning inventory. It has two sections, “Normas de Planeamiento Urbanístico” and
“Instrumentos de desarrollo urbanístico”, with no pagination controls. The live
extraction reads the entire page and all its listed planning PDF documents.
Duplicate icon/title links and the twice-listed norms document are deduplicated.
Six instruments and nine unique PDFs were verified with HTTP 200 and PDF
signatures:

| Instrument | Municipal source documents |
| --- | --- |
| Normas urbanísticas de Membrilla | [Normas](https://membrilla.es/wp-content/uploads/2024/04/NORMAS-URBANISTICAS-MEMBRILLA.pdf) |
| Modificación puntual 1/2022 de las NNSS, UE-5 | [Documento](https://membrilla.es/wp-content/uploads/2026/04/MODIFICACION-PUNTUAL-1-2022-MEMBRILLA.pdf), [oficio](https://membrilla.es/wp-content/uploads/2026/04/OFICIO-DIFERENTES-ORGANISMOS.pdf), [planos 1](https://membrilla.es/wp-content/uploads/2026/04/PLANOS-1.pdf), [planos 2](https://membrilla.es/wp-content/uploads/2026/04/PLANOS-2.pdf) |
| Estudio de detalle manzana M1 sector SI A | [Documento](https://membrilla.es/wp-content/uploads/2024/04/ED-M1-julio-2017.pdf) |
| Estudio de detalle manzana M2 sector SI A | [Documento](https://membrilla.es/wp-content/uploads/2024/04/ED-M2-julio-2017.pdf) |
| Proyecto de reparcelación sector S1 A | [Documento](https://membrilla.es/wp-content/uploads/2024/04/Reparcelacion-S1-A.pdf) |
| Urbanización del tramo de nueva apertura entre Níquel y Pastores | [Proyecto de obra pública ordinaria](https://membrilla.es/wp-content/uploads/2024/04/OPublicaNiquelPastores.pdf) |

The modification and its three annexes occupy one municipal HTML container.
Visual review of the scanned first pages confirmed the same modification 1/2022
on all four documents, including the UE-5 change of category. These are one
instrument, not four projects. The two detail studies concern different blocks
and remain separate instruments. Titles retain the source's S1/SI spelling.

The two detail-study PDFs state “DOCUMENTO PARA INICIO DE TRAMITACIÓN”, July
2017; their narrative's 2005 approval/publication dates concern the antecedent
PAU, not the detail studies. The reparcelación cover says March 2018. The public
works cover identifies the town council as promoter, September 2017, version
18.09.2017; none of these dates establishes approval or completion of those
projects. They are technical documents, not procurement notices or news.

The modification's scanned cover has February 2026 as document date and a
definitive-approval stamp referring to the CPOTyU agreement of 10/12/2025. The
linked oficio is dated 17/03/2026 and refers to the same agreement. The adapter
does not OCR scanned dates or hard-code manually read dates: `fecha`,
`fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` and `fase` remain null.
The `/2024/04/` and `/2026/04/` upload directories and crawl time are never used
as publication or agreement dates. The norms and modification PDF text layers
are empty; local renderings retain evidence of visual inspection.

## Excluded resources and limits

- https://membrilla.es/instancias/ (HTTP 200) contains reusable applications,
  including general and activity forms. These are not granted licences.
- https://membrilla.es/ordenanzas-fiscales/ (HTTP 200) links the fiscal ordinance
  for urban-planning licences, not a concession register. No licences are emitted.
- No comprehensive historical register was established. The adapter does not
  claim completeness beyond this current single-page inventory, legal validity
  of every listed version, construction progress or grant status.
- No coordinates or vector project geometry were extracted. Scanned plans are
  retained as document links; no municipal centroid or jitter is substituted.
  `lat`, `lon`, `geometry` are null and `publication_ready` is false.
- The shared entity policy marks all six current records `pendiente` with
  `insufficient_identity_evidence`: the inventory has no extractable expediente
  references recognized by that policy. Actual instrument/document identities
  are retained without inventing administrative expediente numbers or bypassing
  the policy. This scraper is reviewable but does not establish ingestion or
  map-publication eligibility.

## Implementation and validation

Adapter: `municipio.adapters.membrilla:MembrillaAyuntamientoAdapter`, loaded via
the existing manifest/registry contract. Stable IDs derive from primary PDF
URLs. Each document retains title, role, URL, SHA-256 and byte count. Updates
refresh the entire current snapshot and re-download PDFs, detecting changed
content at the same URL. No incremental date cutoff is imposed.

The parser requires the municipal heading and both sections, rejects unknown
inventory items, ambiguous/unparented annexes and unexpected document URLs, and
fails on pagination rather than silently returning a partial page. Requests
have timeouts and bounded response sizes; HTTP errors, off-host redirects and
non-PDF responses fail before replacing existing output. An initial bare
`requests` PDF request returned HTTP 403; the normal browser-style User-Agent
and municipal Referer used by the adapter returned HTTP 200. No authentication
or credentials were used.

- `python -m unittest municipio.test_membrilla -v`: six offline tests passed,
  covering grouping/deduplication, stable IDs, null date/geometry semantics,
  pagination, changed/login content, annex ambiguity, PDF verification,
  preservation of prior output on failure, manifest loading and disabled licences.
- Real extraction through `load_portal_adapter(load_manifest(...))`: six records,
  nine verified PDFs. Local `evidence/proyectos.jsonl` contains the actual records;
  `evidence/validation.json` records counts, URLs, runtime and limitations.
- `evidence/` also contains the fetched HTML, PDFs, extracted text and first-page
  scan renderings. These are local evidence, not source files to commit.

No shared code, dependencies, database, deployment, publication or Git metadata
were modified. Only the four requested source files are added.
