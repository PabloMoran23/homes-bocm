# Salceda de Caselas — INE 36049, Pontevedra

Verified live on 2026-11-07 using the preinstalled batch venv. This adapter extracts
real planning instruments from the Xunta's SIOTUGA municipal inventory. Coverage
is partial: it is not a municipal project census or a granted-licence register.
Scheduling, licences and missing-coordinate jitter are disabled.

## Official sources inspected

- https://salcedadecaselas.gal/alumeado-e-urbanismo/ — municipal urbanism page,
  currently showing news, including procurement and prospective initiatives.
  It is not used as a project inventory. Procurement notices and unrelated news
  are not emitted as projects.
- https://salcedadecaselas.gal/urbanismo-formularios-e-impresos/ — application forms
  (31 listed items), not evidence of grants. Excluded entirely from extraction.
- https://siotuga.xunta.gal/siotuga/urb — regional planning index identifies INE
  36049, Salceda de Caselas, Normas subsidiarias de planeamento, approval
  1997-02-28; links directly to this municipality's inventory.
- https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36049 — public
  official municipal planning inventory. The anonymous form includes a public CSRF
  value used by its own JavaScript; no login or account credentials are involved.
- https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0 — source
  of the public inventory request protocol and document URL construction.
- https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php — POST
  `id=36049`, `idclase=14/13/18` plus the public form CSRF value. Complete JSON
  arrays: 3 general, 5 development, 0 rural-boundary instruments. JavaScript
  loops through the entire returned array before invoking client-side DataTables;
  no server page parameter exists in this reviewed protocol. No array is sliced.
  Non-array envelopes fail rather than silently lose pagination.
- https://siotuga.xunta.gal/siotuga/assets/inventario/getIOTPU.php — POST `iddoc`,
  `idp=0`, `lang=gl_ES` plus the public form value. Each detail is checked against
  the inventory ID, municipality, title, figure and dates. Component links follow
  the portal's `filesroot + folder + /documents/ + pathesperado` construction.

## Live coverage and semantics

Eight instruments, **131 document links**, grouped by SIOTUGA instrument ID:

| ID | Figure / instrument | Approval | Documents |
| --- | --- | --- | --- |
| 22964 | NSP — Revisión adaptación a LASGA | 1997-02-28 | Attached |
| 22962 | Modificación puntual — NSP núm. 1, ficha SAU.04 | 2000-06-28 | Attached |
| 22963 | Modificación puntual — NSP núm. 2, anexo ordenanza SU-02 | 2000-06-28 | Attached |
| 24511 | Plan parcial — SAUI-04 | 2001-02-21 | Attached |
| 27683 | Plan especial — infraestruturas e dotacións deportivas en Entenza | 2012-08-31 | Attached |
| 26657 | Plan especial — reforma interior UE-02 na Devesa | 2008-09-30 | Attached |
| 27875 | Modificación puntual — PERI da unidade de execución 02 | 2014-04-08 | Attached |
| 24512 | Estudio de detalle — encontro de nova construción con existente | 2003-10-31 | No attachments |

A modification is its own official instrument, while all memories, regulations,
and plan sheets of that instrument remain in one record. The 2014 modification
is not conflated with the original 2008 PERI. No individual sheet becomes a project.
131 links are not 131 projects. The study of detail is retained as a genuine
inventory record with `cobertura_documental=ficha_sin_adjuntos`.

`fechaaddef` becomes `fecha_aprob`; `fechabop`, `fechadog` and
`fechanormativabop` remain separately attributed publication fields. Generic
`fecha` and `fecha_publicacion` are null because these multiple publication dates
are not interchangeable. Upload paths and crawl dates are never approval dates.
Legal incident fields are retained verbatim. No claim of consolidated current
legal validity is made solely from presence in SIOTUGA. `tipo` is the source
figure, not a project phase. IDs are portal identities, not invented expediente
numbers. `source=ayuntamiento` follows the manifest's pipeline source enum;
`organismo_fuente` explicitly identifies the actual publisher, Xunta de Galicia.
Each record retains public POST endpoint provenance and non-session parameters.

Historical class 16 was inspected (one historical NSP entry) and is deliberately
excluded; regional territorial instruments are outside this adapter's scope.
Pending plans, works, municipal news, procurement and licence grants are not
covered. Unsupported figures, identity conflicts and changed response envelopes
fail visibly. Backfill and update both refresh all three supported inventory
classes and all returned detail records, writing only after successful parsing.
No records are silently dropped due to a missing attachment.

No coordinates or verified vector geometry were obtained. Scanned JPG plan
links are retained, but not converted into inferred project boundaries or
centroids. `lat`, `lon`, `geometry` are null and `publication_ready=false`.

## Reproduction and evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_salceda_de_caselas -v
```

Six tests pass: distinct date semantics and document grouping, absent dates and
attachments, arrays larger than a UI page, schema/identity conflicts, municipality
and document-path validation, all-class fetch orchestration and manifest loading.

Real extraction was invoked directly through
`SalcedaDeCaselasAyuntamientoAdapter('salceda-de-caselas',
config={'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
It returned status `ok`, 8 records. `evidence/validation.json` records counts,
source URLs, limitations and checks. `live-inventory*.json`, `live-detail-*.json`
and HTML captures retain the fetched source data. Seven `sample-*.pdf` captures
verify HTTP 200 and PDF signatures, one per instrument with attachments. All
131 attachment URLs are retained, but the remaining attachments were not
individually downloaded or validated. Evidence is local and not source material
for the parser or its tests; it must not be committed.

No shared source files, dependencies, credentials, databases, deployments,
publication commands or git metadata were modified.
