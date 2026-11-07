# Los Corrales de Buelna — Cantabria — INE 39025

Research and live verification: 2026-11-07. This adapter covers the anonymous
municipal transparency inventory, not every planning instrument in the municipality.
No credentials, authenticated dossiers, procurement feeds or news are used as records.

## Official inventories and provenance

- https://loscorralesdebuelna.sedelectronica.es/transparency/ — official municipal
  sede, identifying Los Corrales de Buelna and telephone 942831235. The public
  `9. URBANISMO` folder advertises 13 documents. The root has `Mostrar más`, which
  the adapter also exhausts before selecting the Urbanismo folder.
- https://loscorralesdebuelna.sedelectronica.es/transparency/fa566751-d548-457e-8d4d-b233ffe585be/
  — current Urbanismo inventory: two individual environmental documents and one
  PGOU folder containing 11 documents. Discovered through the public Wicket
  callback and its `Ajax-Location` header; no session tokens are hardcoded.
- https://loscorralesdebuelna.sedelectronica.es/transparency/682ace35-d790-4dab-b57d-897ab0e5dcf3/
  — `PUBLICACION EN EL BOC APROBACION DEFINITIVA PGOU 2015`. Initially displays
  10 documents, then `Mostrar más` supplies document `2015-1484 (10)`. All 11
  stable `preview-document` links belong to one PGOU record, not 11 projects.
- https://loscorralesdebuelna.sedelectronica.es/preview-document/d759d74f-49fe-4dcc-8693-b07a3f234401
  — `2019-95 Anuncio informe Ambiental Estratégico de la Modificación Puntual
  Número 1 del PGOU`. Identifies MP1; environmental report is the documented
  phase, without claiming final approval of the modification.
- https://loscorralesdebuelna.sedelectronica.es/preview-document/a6fcb684-f53e-4530-bca0-fc7e4eca319b
  — scoping document for the environmental assessment of the Plan Parcial,
  sector de suelo urbano no consolidado nº 10. Identifies a real planning
  instrument, with environmental scoping phase, not approval or a licence.
- https://loscorralesdebuelna.sedelectronica.es/preview-document/cea2e130-afed-41a5-940c-2fff28a6a10a
  — first PGOU document. PDF contains CVE-2015-1484, publication 2015-02-13,
  CROTU agreement 2014-12-05 and municipal remittance agreement 2014-12-18.
  These are distinct events. The inventory parser does not parse PDF text, so
  none of these dates are inserted as extracted dates. MP1 PDF publication is
  2019-01-14; likewise left null in automatic output. The downloaded SUNC-10
  PDF is image based (`pdftotext` yields no textual content).

The 13 stable preview links are retained in `documentos`, including original
source labels. Preview pages expose PDF iframes. Live validation checks every
preview link, while local evidence also contains downloaded example PDFs and
text captures used to verify provenance. Temporary signed iframe paths are not
used as persistent identifiers.

The service catalogue at
https://loscorralesdebuelna.sedelectronica.es/citizen-service/ecca9493-1833-4913-85ff-2c0b5adf4986
and the public board at https://loscorralesdebuelna.sedelectronica.es/board/
were inspected separately. Service requests and licence applications are not
proof of granted licences. They are outside this adapter's extraction scope.

## Exclusions and partial coverage

The similarly named https://transparencia.loscorrales.es/ belongs to Los Corrales
in Sevilla (address Plaza de Diamantino García 13, telephone prefix 955).
It is explicitly excluded; its plans must not contaminate Cantabria's records.
The municipal homepage https://www.loscorralesdebuelna.es/ returned no useful
HTML inventory in this investigation; `/urbanismo` returned 404.

Official BOC notices
https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=424227 and
https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=424229 describe
initial approval of MP2A and MP2B on 2025-07-31, published 2025-09-09. They
are absent from the reviewed transparency folder and outside the implemented
inventory coverage. Therefore the three extracted instruments must not be
presented as a comprehensive or fully up-to-date planning register. Environmental
or publication phases are evidence of those documents, not assertions that no
later agreement exists. Procurement announcements and unrelated news are excluded.

## Implementation and verification

The adapter implements the four `AyuntamientoAdapter` methods; licence methods
write an empty disabled result. Update refreshes a full inventory snapshot.
Manifest schema and the existing portal, Hernani and Manlleu examples were
reviewed first. No shared source or dependency changes are needed.

Requests use an anonymous session, explicit timeout and official-host validation.
Wicket URLs are read from current markup; XML components are parsed as data,
never executed as JavaScript. Pagination is exhausted, duplicates and loops fail,
and both Urbanismo recursive total and PGOU document counts must agree. A safety
limit raises instead of returning a truncated snapshot. Unknown document/folder
semantics fail for review. Output is replaced only after successful extraction.

All exact date fields remain null because the inventory supplies no structured
exact dates. Neither crawl time, `2015` in the folder title nor `2019-95` in a
filename is an agreement/publication date. PDF date extraction is outside scope.
No parcel or municipal centroid is substituted for geometry: lat/lon/geometry
are null and publication_ready is false. `schedule.enabled=false`,
`geocode.jitter_missing=false`, `licencias.enabled=false`.

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_los_corrales_de_buelna -v`: 9 offline tests pass;
  covers pagination including the eleventh document, loops, login/empty content,
  grouping, date semantics, unrelated records, external links, disabled licences
  and preserving output on a count mismatch.
- Live extraction through manifest loading and `load_portal_adapter`: 3 records,
  13 documents; all 13 preview pages checked for PDF viewers.
- Local `evidence/proyectos.jsonl`, `evidence/validation.json`, HTML/XML captures
  and example PDFs document the run. Evidence is local and is not source to commit.

Ready for independent review only; accepted=false. No publication or deployment.
