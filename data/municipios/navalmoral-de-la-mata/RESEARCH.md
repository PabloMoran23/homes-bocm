# Navalmoral de la Mata — INE 10131, Cáceres, Extremadura

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Implemented coverage is deliberately partial: one real new Plan General Municipal
(PGM) instrument, grouping all four PDF documents currently listed on its municipal
page. This is documentation of preparation and participation, not evidence of a
legally approved new plan or a granted licence. `publication_ready` is false.

## Official discovery and provenance

- https://www.aytonavalmoral.es/areas-tematicas/urbanismo/ — HTTP 200;
  municipal urbanism gateway. Links to transparency, SITEX planning, ADI-CA,
  application forms and electronic procedures. Its news cards and application
  forms are not emitted as planning/project/licence records.
- https://www.aytonavalmoral.es/tramites/plan-general-municipal/ — HTTP 200;
  actual named new PGM with a participation narrative and DOCUMENTACIÓN section.
  That complete section, rather than a news feed or navigation menu, supplies the
  instrument and its four attached PDFs. No pagination is present. There is no
  date-based cutoff or record limit. The adapter rejects pagination markers or
  unexpected document links rather than silently omit another page or resource.
- https://aytonavalmoral.sedelectronica.es/transparency/1933317d-da93-4b89-af0d-46a7f9ac878d/
  — HTTP 200; Wicket expandable inventory tree reports 13 planning, 44 urban
  execution, 3 works/infrastructure, 5 environmental, 9 indicator and 21 form
  documents. Those counters are not extracted records; branches were not
  traversed and are explicitly outside this adapter's coverage. The chosen PGM
  page is not asserted to replace or exhaust this inventory.
- http://sitex.gobex.es/SITEX/planeamiento — official regional planning link from
  municipal gateway; HTTPS equivalent timed out during discovery. No claim is
  made about the currently legally operative instrument in SITEX.
- https://www.aytonavalmoral.es/navalmoral-de-la-mata-avanza-en-la-elaboracion-de-su-plan-general-municipal/
  — HTTP 200; corroborates the PGM preparation process and fourth working meeting.
  This news item is not emitted as a second project.

## Instrument and documents

All links retain the exact source label, original municipal HTTP URL and parent
page in `documentos`. Stable instrument identity uses the municipal PGM page URL,
so adding a presentation does not create another project. Repeated exact document
URLs are deduplicated. The four source attachments are:

1. `2025/07/2025-04-28_PGM-Navalmoral-de-la-Mata_Presentacion-equipo.pdf`
2. `2025/07/2025-06-17_PGM-Navalmoral-de-la-Mata_Sistemas-v6.pdf`
3. `2025/10/2025-09-23_PGM-Navalmoral-de-la-Mata-Vivienda-y-Actividad-Economica.pdf`
4. `2025/10/2025-09-23_PGM-Navalmoral-de-la-Mata-Viviendas-irregulares.pdf`

All reside below `http://www.aytonavalmoral.es/wp-content/uploads/`; all four
were downloaded successfully using HTTPS for evidence, with original and retrieval
URLs plus SHA-256 digests recorded in `evidence/validation.json`. The first PDF's
cover explicitly describes a public presentation of the drafting process and
citizen participation activities, dated 28 April 2025. Local `pdftotext` output is
retained in `evidence/presentacion-equipo.txt`.

The last two link labels say **23 October 2025**, while their filenames contain
**2025-09-23**. Neither is silently corrected or interpreted as a publication,
agreement or approval date. The upload-directory month is also not a publication
date. Record-level `fecha`, `fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob`
are null. The web page's generic explanation of a PGM's legal function is not
interpreted as proof that this new plan has been approved. The phase records the
participation activity actually described by the source.

## Contract and validation

The manifest follows `municipio/manifest.py` and uses the four methods in
`municipio/adapters/portal.py`. `schedule.enabled`, `geocode.jitter_missing` and
`licencias.enabled` are false. No coordinates, parcel polygons or municipal
centroids are substituted: `lat`, `lon` and `geometry` are null. Licence methods
return a disabled empty result. Incremental update refreshes the whole single-plan
snapshot; it does not manufacture an update timestamp or agreement date.

Live fetching uses a 40-second timeout, a streamed 3 MB response bound, HTTP status
and HTML content-type checks, and exact expected source URL validation. Parsing
requires the named plan, municipality, participation narrative and a single
DOCUMENTACIÓN section containing same-host PGM PDFs. Missing content, ambiguous
sections, external/unrelated document provenance and changed pagination fail
before the output is replaced.

Validation performed:

- `python -m unittest municipio.test_navalmoral_de_la_mata -v`: **7 tests passed**.
  Checks grouping, preserved provenance, unknown dates/geometry, stable identity,
  empty/login/form rejection, missing participation, unexpected documents,
  pagination rejection, manifest loading and disabled licences.
- Real extraction through `load_portal_adapter(load_manifest(...))`: **1 live
  record, 4 attached documents**; stored in `evidence/proyectos.jsonl` with the
  exact response in `evidence/pgm-live.html` and audit details in
  `evidence/validation.json`. The shared entity policy labels the broad planning
  instrument `pendiente / insufficient_identity_evidence`, activity ineligible;
  its annotation is preserved. No policy exception is introduced.
- All four PDFs independently fetched successfully; discovery HTML captures are
  also local under `evidence/`. Evidence is not a source change to commit.
- No shared modules/dependencies, credentials, databases or deployment services
  were touched. Only the four requested municipal source files were added.

Remaining limitations: no complete historic planning/works inventory, no granted
licence register, no verified agreement/approval/publication dates, no geometry.
The source is useful for an auditable real instrument snapshot, not a complete
municipal or map-ready dataset. Acceptance remains for independent review.
