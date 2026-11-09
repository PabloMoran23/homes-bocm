# Moraña — Pontevedra — INE 36032

Verified 2026-11-09 using the preinstalled Python runtime. One adapter, with
partial coverage of actual planning instruments, supplied by the official Xunta
SIOTUGA municipal inventory. Moraña (36032) is not Moaña (36029).

## Discovery and source selection

- Municipal website: https://morana.org/ and
  https://morana.org/novo-pxom-do-concello-de-morana/ and
  https://morana.org/normativa-plan-xeral-vixente/ returned HTTP 403 from Python.
  The www and es hosts failed network connection from this environment. Search
  discovery identifies a newer PXOM initially approved in 2013, but that search
  excerpt is not used to manufacture a record or assert its current status.
  Local discovery responses are under `evidence/discovery-*.html`.
- https://morana.sedelectronica.gal/info.0 returned HTTP 200. The visible
  urbanistic licence requests, declarations, health/safety approval application
  and other procedure forms are not granted licences or physical works. No
  public granted-licence register was verified. Capture: `official-3.html`.
- https://territorioeurbanismo.xunta.gal/es/territorio-y-urbanismo/registro-de-ordenacion-del-territorio-y-urbanismo/buscador
  returned HTTP 200 with a filterable official registry. The unfiltered global
  results are not ingested. Its Moraña filter uses internal value 483, not INE.
  Capture: `official-2.html`.
- **Selected source:**
  https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=36032
  returned HTTP 200. Its municipality option explicitly associates 36032 with
  Moraña. The similarly named `inventario.php?mun=36032` only opens the search
  shell; the adapter uses the site's actual `inv=1&idconcello=36032` route.
- The site's public client implementation,
  https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0,
  identifies the inventory and dossier endpoints and how to build attachment
  URLs. Captured in `evidence/inventario.js`. The anonymous form's anti-CSRF
  field is obtained afresh; no account, authentication or private API is used.

## Actual extraction and pagination

POST `assets/inventario/query_document.php` under the SIOTUGA base, with
`id=36032`, the public form field and `idclase`:

- 14 (general planning): 22877, PLAN XERAL DE ORDENACIÓN MUNICIPAL;
  22878, Modificación Puntual / PXOM.
- 13 (development planning): 23996, POLIGONO INDUSTRIAL DE MIRALLOS;
  23997, SOLO INDUSTRIAL EN DESENVOLVEMENTO. Both are Plan Parcial.
- 18 (rural nucleus delimitation): JSON null, no entries.

The site renders **all returned array entries** using client-side DataTables.
There is no page/limit parameter or server-side pagination in this client path.
The adapter requests each selected class, consumes every returned item, and
rejects unexpected envelopes (including paginated objects), duplicate IDs,
foreign municipality details, conflicting dates or documents missing from a
planning instrument. No slicing or record limit is applied.

For each inventory row, POST `assets/inventario/getIOTPU.php` with `iddoc`,
`idp=0`, `lang=gl_ES` and the public form field. The detail's `menutitle`, `id`
and `folder` must agree with Moraña and the inventory ID. Provenance in every
record specifies endpoint, method and non-session parameters. Stable IDs derive
from these actual SIOTUGA dossier IDs; they are not municipal expediente numbers.

All attachment groups and components are retained in `documentos`, including
labels, source component IDs and direct links. One instrument produces one row,
not one row per PDF/map. Live extraction: **4 instruments, 159 document
references** (105, 6, 23 and 25 respectively). The source repeats the same PXOM
rural-study filename for fichas 12 and 13; both labelled references are preserved,
without inventing a corrected path. A sample document was fetched successfully:
https://siotuga.xunta.gal/siotuga/documentos/urbanismo/MORANA/documents/0835no001.pdf
(HTTP 200, application/pdf, 186537 bytes), saved locally. Availability of all 159
references has not been verified.

## Dates, provenance and coverage limits

`fechaaddef` maps to `fecha_aprob`; `fechadog` maps to `fecha_publicacion`
with `canal_publicacion=DOG`; BOP and BOP normative publication dates remain
separate. Generic `fecha` stays null, missing dates stay null. Inventory and
detail dates must agree. Approval dates are 2001-08-03, 2002-06-07, 2002-08-02
and 2002-04-18 respectively. These are source approval dates, not crawl dates.
No additional agreement date or execution phase is inferred. Legal observations
are retained; definitive approval metadata alone does not establish today's
legal validity or prove the inventory is up to date.

This is a snapshot of the selected SIOTUGA urban-planning classes, not complete
municipal coverage. Historical class 16 was checked (null) and is deliberately
excluded. The territorial instrument inventory was also inspected and captured
in `territorial-inventory.json`; broader regional instruments are outside this
adapter's scope. Recent pending modifications, the municipal new-PXOM material,
physical works and public notices outside this inventory are not covered. No
procurement announcement, unrelated news or application form becomes a project.

The manifest uses the existing pipeline's `ayuntamiento` source mode, while
records explicitly identify the effective source as `xunta` and SIOTUGA. There
are no verified vector geometries or project coordinates: `lat`, `lon` and
`geometry` remain null, `publication_ready=false`. Scheduling, coordinate jitter
and licences are disabled. Updates refresh the complete snapshot; failed fetches
or parsing leave existing output untouched.

## Validation

Run from repository root:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_morana -v
```

Seven offline tests passed: grouped documents and date semantics, missing dates,
municipality/identity/date conflicts, invalid/missing documents, changed inventory
shape/pagination/duplicates, failed-request snapshot preservation, and manifest
loading with disabled licences. Fixtures are small source-shaped examples and do
not make network requests. Actual live extraction used `load_manifest('morana')`
and `load_portal_adapter`, then `backfill_proyectos`, exercising the real registry
and shared entity annotation wrapper. Four records written successfully.

Local, uncommitted evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`inventario.html`, inventory JSON responses, four detail JSON responses, discovery
captures and the sample PDF. Validation includes live record count, source URLs,
limitations and runtime. Shared entity policy reports four unknown categories;
that classification is retained rather than inventing a building-use category.
Only the four requested source files are added; no shared code/dependencies or
git metadata are changed, and no publication/deployment operation is performed.
