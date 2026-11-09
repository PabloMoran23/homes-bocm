# Yebes — Guadalajara — INE 19326

Verified 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One adapter, deliberately partial coverage: four genuine planning/project
instruments, 17 document references. No granted licences or inferred geometry.

## Official source discovery

- https://www.aytoyebes.es/servicios/urbanismo-e-infraestructuras/
  returns HTTP 200, but lists existing facilities and service information. These
  are not project dossiers and are excluded. Its navigation links to the municipal
  electronic headquarters, establishing provenance.
- https://yebes.sedelectronica.es/transparency returns HTTP 200 and exposes the
  public category “7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE” (32 documents).
  Expanding its anonymous Wicket link returns the public destination through the
  `Ajax-Location` response header. No authentication is needed.
- https://yebes.sedelectronica.es/transparency/18d47a90-5cca-4c36-8320-64d40729eefb/
  is that urbanism inventory, with eight categories. The adapter selects four
  categories explicitly; it does not claim all 32 documents or all municipal works.

## Extracted instrument inventory

| Source folder | Instrument | Document links |
| --- | --- | --- |
| [7.1](https://yebes.sedelectronica.es/transparency/8ed49797-40d3-47cc-a45a-6ab12d1d7fdf/) | Modification 2 of the POM | 5 |
| [7.5](https://yebes.sedelectronica.es/transparency/e9b0d219-9c1b-4c8a-ba8a-a28896a67238/) | Calle Eras–Cementerio urbanization project, including transformer annex | 2 |
| [7.7](https://yebes.sedelectronica.es/transparency/33463117-3e69-44d5-8384-45abe5e3eedd/) | Modification 3 of the POM | 8 |
| [7.8](https://yebes.sedelectronica.es/transparency/380c5112-50f0-4078-8985-5ca750cf30f3/) | `26004_MpPP nº 2 S1 Yebes`: modification 2 of sector 1 partial plan, in processing | 2 |

Each row becomes one instrument, not one record per PDF. Modification 3 includes
four documents in the nested folder
https://yebes.sedelectronica.es/transparency/ba77d7f7-2ead-4d89-9e71-41500fd1b29b/
(“Documentación de la modificación aprobada por el Pleno”), plus four at its root.
Different versions remain together, each with its exact source title,
`preview-document` URL and containing `inventory_url`. No version is silently
asserted to supersede another. Preview URLs are official document references;
they are not represented as downloaded PDF bodies. Record identity is derived
from the stable instrument folder URL, never a session callback or document count.

Categories 7.2 (environmental plans), 7.3 (urban regulations with POM and sector 1
subfolders), 7.4 (urban agreement), and 7.6 (urban qualification) were inspected
but excluded from this deliberately scoped extraction. Forms, procurement notices,
existing facilities, general news and budget changes are excluded. No public
register of granted licences was established.

## Dates and legal status

The inventory supplies document titles, not reliable structured agreement or
publication dates. A date embedded in an announcement filename/title such as
`20210724` is retained in the source title, not interpreted as approval.
`fecha`, `fecha_acuerdo`, `fecha_publicacion` and `fecha_aprob` remain null.
Only folder 7.8 explicitly establishes “en tramitación”; other phases remain
unknown rather than inferred from individual document titles or folder placement.

A separate official BOP source was discovered:
https://boletin.dguadalajara.es/boletin/index.php/2-anuncios/63056-APROBACI%C3%93NDEFINITIVAMODIFCACI%C3%93NPUNTUALN%C3%9AM3DELPLANDEORDENACI%C3%93NMUNICIPALDEYEBES
It distinguishes the 2025-07-17 commission agreement, initially subject to
corrections, subsequent DOCM publication on 2025-11-13 and BOP publication on
2025-12-15. Those events are not automatically merged into the inventory records.
The adapter does not assert that an inventory document is the final approved
version or that a work is executed. Coverage is of documents publicly listed now,
not a complete chronology or legal certification of current planning.

## Extraction and validation

The adapter uses an anonymous requests session and follows public folder callbacks
without evaluating JavaScript. Requests have a 35-second timeout; source hosts,
folder destinations, markup, nonempty inventories, duplicate documents and
recursive folder counts are checked. Every selected folder's total must equal
its advertised document count. Recognized pagination/“Mostrar más” raises an
error; the adapter does not silently take the first page. Generic folders 7.1 and
7.8 also require document titles to match the scoped instrument. Changed markup,
new unrelated instruments, cycles or incomplete results fail before output is
replaced. Updates refresh the full scoped snapshot, not a date-based increment.

- `python -m unittest municipio.test_yebes -v`: five tests passed, covering grouped
  documents and nested provenance, stable IDs, unknown dates/geometry, partial
  count rejection, pagination/login/external-link rejection, missing instruments,
  manifest loading and disabled licences.
- Actual `YebesAyuntamientoAdapter.backfill_proyectos` live run: 4 records,
  document counts 5 / 2 / 8 / 2. All selected inventories returned HTTP 200.
- Local `evidence/proyectos.jsonl`, `evidence/validation.json` and
  `evidence/captures/*.html` retain the actual extraction and source captures.
  Additional discovery captures are under `evidence/`. Evidence is not source
  code and must remain uncommitted.

No verified geometry is extracted. Coordinates and geometry are null,
`publication_ready` is false, `geocode.jitter_missing` is false,
`licencias.enabled` is false and `schedule.enabled` is false. No shared files,
dependencies, database, credentials, deployment or publishing operations are
needed for this adapter.
