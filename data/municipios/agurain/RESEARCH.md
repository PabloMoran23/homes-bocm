# Agurain / Salvatierra — INE 01051, Álava

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Candidate scraper with deliberately partial coverage: the complete municipal
**Planeamiento de desarrollo** card. Six genuine planning instruments, grouped
with 47 document links. This is neither a complete historical planning register
nor an inventory of granted licences. Scheduling and coordinate jitter are disabled.

## Official inventories reviewed

- Municipal Urbanismo inventory:
  https://agurain.eus/es/servicios-municipales/urbanismo — live HTTP 200.
  Separately exposes general planning, development planning, municipal works,
  urbanisation projects and other urban-management documents. The adapter selects
  the development-planning card by its exact heading and visits every link in
  its content list. It has no pagination on the verification date. Unexpected
  pagination or unsupported links cause failure; there is no result-count cap.
- The general-plan card links to a generic provincial search, describes the PGOU
  and three modifications, and links an ordinance change and a participation
  programme for the fourth structural modification. These are outside this
  adapter's coverage. Descriptive text alone is not emitted as a plan record.
- The same page lists Egileor parking works and urbanisation documents for
  Curtidos Harresi, Erillas de San Juan and Mezkia water supply. These are useful
  official inventories but outside this adapter's development-planning scope.
  A public-information or procurement announcement does not evidence construction
  completion or a granted licence. No news/procurement crawler is used.
- Provincial planning register, linked directly by the municipality:
  https://web.araba.eus/es/urbanismo/planeamiento-urbanistico
  — detail records provide municipal identity, asiento, expediente, approval
  metadata and downloadable-document URLs, where available. The adapter visits
  the municipality's exact detail links rather than claiming complete coverage
  of the province-wide search.

## Extracted instruments and provenance

| Instrument | Official source | Approval date | Documents |
| --- | --- | --- | --- |
| AIU-5 Opakua urbano | https://web.araba.eus/es/urbanismo/planeamiento-urbanistico/-/reg/2021-444 | 2021-04-29 | 3 |
| AIU-17 Cementerio | https://web.araba.eus/es/urbanismo/planeamiento-urbanistico/-/reg/2022-460 | absent | 0 |
| AIU-5 San Jorge | https://web.araba.eus/es/urbanismo/planeamiento-urbanistico/-/reg/2021-424 | 2020-07-23 | 3 |
| Parque fotovoltaico Ekiola | https://web.araba.eus/es/urbanismo/planeamiento-urbanistico/-/reg/2023-001 | 2022-12-22 | 10 |
| AIU4 Educativo-Deportivo | https://web.araba.eus/es/urbanismo/planeamiento-urbanistico/-/reg/2024-013 | 2024-06-27 | 30 |
| 1ª modificación del PERI del casco histórico | https://www.araba.eus/BOTHA/Boletines/2026/052/2026_052_01226_C.pdf | 2026-01-29 | 1 |

The first five are HTTP 200 registry HTML detail pages. Their exact registry
titles, municipal inventory titles, raw metadata and official expediente numbers
are preserved. Registry dates explicitly labelled `Fecha de aprobación` populate
`fecha_aprob`; generic `fecha`, publication and agreement dates remain null.
The approval heading and agreement type establish the recorded definitive phase.
This describes the published planning instrument, not a construction permit.

The cemetery entry is real (asiento 2022/460, expediente AHI 076/22), marked
Vigente and under Aprobación definitiva, but its approval-date field is empty and
it exposes no document links. Neither dates nor attachments are invented.

Opakua's BOTHA label says `BOTHA Nº 114 (24/01/2022)` while its target is
`/BOTHA/Boletines/2021/114/2021_114_03224_C.pdf`. The adapter preserves that label
and target in `referencias_publicacion_registro` and deliberately leaves
publication null for registry entries. It does not resolve the inconsistency by
choosing either date. Other registry BOTHA labels also remain raw references,
not independently verified publication dates.

The sixth source is a genuine nine-page BOTHA PDF (HTTP 200, application/pdf).
The existing system `pdftotext` executable extracts its text locally; no package
installation or dependency edit is required. Parser assertions require the
municipality, actual definitive-approval act, named historic-centre instrument,
registry asiento and explicit dates. The bulletin identifies asiento 2026/4,
the council agreement of **29 January 2026**, publication on **8 May 2026**,
registration on 6 March and signature on 24 April. Only the agreement and
publication dates populate their respective fields; the signature is not used
as approval. Text excerpts supporting those dates are retained in the record.
The source's asiento is a registry identifier, never an invented expediente.

## Grouping, boundaries and operation

Stable record IDs derive from official asientos, not scrape order or timestamps.
Every attachment remains under its instrument with its title, URL and provenance
page. This includes `data-download` URLs used by the registry's JavaScript UI,
not useless `href="#"` placeholders. Document URLs are deduplicated. Technical
files and certificates are linked, not downloaded or emitted as separate projects.
If another inventory link resolves to the same asiento, documents are merged;
conflicting approval dates fail the extraction. A full snapshot is written
atomically only after all inventory entries succeed. Updates repeat this complete
bounded-scope snapshot; they do not silently apply a page or record limit.

HTTP requests have a 40-second timeout and a 10 MB per-response limit. Exceeding
the limit raises an error rather than parsing a truncated response. The small
BOTHA PDF is converted with a 30-second subprocess timeout. The runtime requires
the already installed `pdftotext`, plus the repository's existing requests and
BeautifulSoup dependencies. Missing executable, source failures, login shells,
changed identity or unreviewed inventory links fail extraction.

No project geometry is verified. `lat`, `lon` and `geometry` remain null;
`publication_ready` is false. No municipal centroid or synthetic coordinates are
substituted. Granted licences are disabled and licence methods produce an empty
disabled result. The common registry wrapper applies the existing entity policy:
five referenced dossiers are eligible expediente records; the PDF-only sixth
instrument remains classified as a document by that shared policy, despite its
explicit planning act. No shared classification rule is modified to bypass it.

## Validation and local evidence

- `.../venv/bin/python -m unittest municipio.test_agurain -v`: 10 tests pass,
  covering scope and duplicate links, pagination/unsupported-link rejection,
  grouping of download URLs, municipal/registry identity, absent and invalid
  dates, agreement versus publication/signature dates, disabled licences,
  snapshot updates and preservation of prior output on partial-fetch failure.
- A real extraction through `load_manifest`, `load_portal_adapter` and
  `backfill_proyectos` returns six records and 47 document links. No fixture or
  fallback record is used in that run.
- Local `evidence/proyectos.jsonl`, `evidence/validation.json`, entity-policy
  report, municipal HTML, five registry HTML captures and BOTHA PDF/text capture
  document the run. `validation.json` records live count, fetched source URLs,
  timestamp, parser-test results and coverage limitations. Evidence is local and
  is not part of the four source files.
- No publishing, database access, credentials, shared-source changes or dependency
  changes are involved.
