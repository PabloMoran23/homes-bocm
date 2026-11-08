# Muro — INE 07039, Illes Balears

## Sources and municipal identity

Reviewed on 2026-11-08. This is Muro, Mallorca, not Muro/Muro de Alcoy in
Alicante. The official portal is https://ajmuro.net, whose municipal urbanism
page identifies the town hall at Plaça Comte d'Empúries, 1, 07440 Muro.
Reviewed the existing adapters, `municipio/adapters/portal.py`, registry and
`municipio/manifest.py` before implementing this municipality only.

Discovered through the official [Documents directory](https://ajmuro.net/ca/arxius-i-documents/documents):

- [Pla general d'ordenació urbana](https://ajmuro.net/ca/arxius-i-documents/pla-general-dordenacio-urbana):
  one actual instrument folder and one urban-information viewer link. The folder
  contains an Estudi de Detall for volume arrangement at carrer Bisbe Massanet,
  28. Its three child pages expose Memòria, Plànol situació and Documentació
  gràfica, with PDF links 297510.pdf, 297511.pdf and 297512.pdf. These are three
  documents belonging to **one** instrument, not three projects. The inventory
  label does not justify inventing a separate approved general plan record.
- [Exposició Pública](https://ajmuro.net/ca/arxius-i-documents/exposicio-publica):
  26 entries across two pages (`?page=1` is the second). One explicitly titled
  detail study: EXP. 2/2018, landscape and volume integration of a detached
  dwelling at parcel·la 443, polígon 13. Six PDFs on its detail page are retained
  together: Estudi de detall, Memòria descriptiva and four modified plans.
  Public-exposure status comes from the instrument title; it establishes neither
  a final approval nor a granted building licence.
- [Urbanisme documents](https://ajmuro.net/ca/arxius-i-documents/urbanisme):
  five application/notification/construction responsibility forms. Excluded;
  none constitutes a granted licence.
- [Urban-information link](https://ajmuro.net/ca/enlla%C3%A7os/pla-general-dordenacio-urbana/sistema-dinformacio-urbanistica-de-muro)
  points to https://sitmun.idelma.cat/urb_muro, which redirected during research
  to `/visorSitmun/inicio3.jsp`, an HTML/JavaScript viewer. No verified export
  or project geometry was extracted from it.

## Extraction contract and limits

The adapter refreshes both document inventories as a complete snapshot and
follows all pagination links within each inventory path, including navigation
backwards. Repeated pages are deduplicated; a safety bound raises an error
instead of emitting partial output. Missing inventory markup, missing documents,
changed attachment counts or unexpected external URLs also fail the run. Rows
are written atomically only after both inventories have been processed.

Only entries explicitly naming an `Estudi de Detall` are included. The Hotel
Playa Esperanza exposure entry does not identify an instrument in its title and
is outside this parser's coverage. A concession contract mentioning water-service
works is a procurement entry and is excluded. Ordinances, taxes, personnel,
property sales, news and reusable forms are excluded. This is partial coverage
of documentary planning instruments, not a complete register of municipal works,
licences or all planning proceedings. Minutes and other portals are not crawled.

Every instrument retains its municipal detail URL, originating inventory,
PDF links, document titles and the specific document landing pages. The portal
shows `01/10/2018` on the three Bisbe Massanet file cards; the other instrument's
file cards show `10/06/2019` and `03/07/2019`. Their meaning is unspecified, so
these are stored only as `fecha_documento_portal`, with an explicit semantics
field. Generic, publication, agreement and approval dates remain null. The
adapter does not parse legal decisions from PDF text. Historical publication in
an accessible archive does not establish present validity. Coordinates and
geometry are null; `publication_ready` is false. Licence extraction and scheduling
are disabled and missing locations are never jittered.

## Validation and local evidence

Use the preinstalled runtime:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_muro -v
```

Five offline tests cover inventory scoping, pagination, document grouping,
reference extraction, date semantics, invalid sources/forms, full refresh and
preserving previous output on incomplete retrieval. Live extraction uses
`load_manifest('muro')` and `load_portal_adapter(manifest).backfill_proyectos(...)`,
therefore exercising the shared adapter contract and entity annotation.

Local evidence lives under `evidence/` and is not committed: `proyectos.jsonl`,
`validation.json`, HTML captures and linked PDF captures. The validation file
records the live record count, fetched source URLs, attachment checks and
coverage limitations. No dependencies or shared source files were changed.

The shared entity policy leaves Bisbe Massanet as `pendiente` with
`insufficient_identity_evidence` because the HTML archive gives no municipal
expediente identifier; no reference was manufactured to bypass that guard. The
referenced EXP. 2/2018 is annotated as an expediente. This does not change the
fact that both records represent documented planning instruments, and neither
is presented as a granted licence or ready for geospatial publication.

Live validation produced **2 records**, grouping **3 + 6 = 9 PDF documents**.
All nine PDF downloads were verified by their PDF signature and saved locally;
one transient read timeout succeeded on a bounded retry. HTML extraction itself
completed successfully. `evidence/validation.json` includes each PDF result and
all 18 fetched HTML/document URLs. Parser tests passed 5/5.
