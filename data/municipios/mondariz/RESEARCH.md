# Mondariz — INE 36030, Pontevedra

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
This adapter covers a municipal planning inventory, with three genuine instruments.
It does not claim complete municipal project coverage. It explicitly excludes
Mondariz-Balneario (INE 36031).

## Discovery and official provenance

- Municipal website: https://concellodemondariz.gal/ (HTTP 200). The home page
  exposes old news, including procurement/service announcements, not a project
  register. https://concellodemondariz.gal/accion-de-goberno/ (HTTP 200) lists
  plenary minutes from 2019; it is not parsed into projects.
- Current municipal electronic headquarters:
  https://mondariz.sedelectronica.gal/info.0 (HTTP 200). Under
  **PLANEAMENTO URBANISTICO**, “Proxecto de Ordenación do Medio Rural” links to
  https://siotuga.xunta.gal/siotuga/inventario . The other planning link is the
  regional Plan Básico Autonómico viewer. Licence applications in the service
  catalogue are forms, not evidence of grants; they are excluded.
- SIOTUGA official manual: https://siotuga.xunta.gal/siotuga/axuda (HTTP 200).
  Describes municipal inventories of approved planning, separating general,
  development, historical and rural-settlement instruments, and territorial plans.
- Direct municipality inventory:
  https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=36030 (HTTP 200).
  The actual current UI script `assets/inventario/controls.min.js?2.5.0`, captured
  locally, identifies the public AJAX requests. The adapter reproduces these
  anonymous read-only queries, with a fresh public form/CSRF token and session.
  No account, password or private credential is used.

## Extraction scope and results

POST `https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php`,
with `id=36030` and `idclase` 14, 13, 18 respectively, returns full JSON arrays
(or null for an empty class). The portal passes the complete array into local
DataTables pagination. There is no server page-size parameter or truncation in
this adapter. Unexpected envelopes fail, rather than accepting the first page.
All three classes are queried on each refresh. Historical class 16 was inspected
and captured separately during research but is deliberately excluded (two rows).
Territorial/supramunicipal plans are outside this adapter's scope.

Each instrument's detail is fetched through POST
`https://siotuga.xunta.gal/siotuga/assets/inventario/getIOTPU.php`, using its actual
`iddoc`, `idp=0`, `lang=gl_ES`. IDs, document directory, municipality and dates must
agree with the inventory. The JSONL retains endpoint and POST parameter provenance,
without persisting the temporary form token in records.

| SIOTUGA ID | Instrument | Definitive approval | DOG publication | BOP publication | Distinct document links |
| --- | --- | --- | --- | --- | --- |
| 22873 | Proxecto de Ordenación do Medio Rural | 1999-02-26 | 1999-05-28 | 1999-06-01 | 82 |
| 22874 | Modificación Puntual: POMR | 2001-08-30 | 2002-03-13 | 2001-11-16 | 4 |
| 26838 | Estudio de Detalle: relativo ao reaxuste das aliñacións na Avenida do Balneario de Mondariz | 2005-08-25 | 2005-09-30 | absent | 0 |

These old approval dates are returned by the current approved-planning inventory;
this does not assert recent construction or a new approval. The detail for 26838
explicitly identifies Mondariz despite the street's name. Its `elementos` is null:
it is a real inventory record, with `sin_documentos_en_ficha`, not an invented PDF.
The POMR has 83 components representing 82 distinct URLs. Attachments are grouped
under their instrument, never emitted as separate projects. All distinct links
are retained, including scanned JPG plans, with source document descriptions.
One representative normative PDF, `0830no100.pdf`, was fetched successfully and
its PDF signature checked; other linked files were not individually downloaded.

`fecha_aprob` comes only from `fechaaddef`. `fecha_publicacion` explicitly denotes
DOG, with BOP and normative BOP dates in separate fields. Generic `fecha` and
`fecha_acuerdo` remain null; the inventory does not establish a separate agreement
date. Crawl time is never substituted. Identity uses actual SIOTUGA instrument IDs.

## Limitations and validation

No granted-licence register was verified. Public works, announcements, plans still
in processing, historic instruments and regional territorial instruments are not
covered. No instrument geometry was retrieved or verified: `lat`, `lon`, and
`geometry` remain null, `publication_ready=false`, and jitter and scheduling are
disabled. The manifest sets `licencias.enabled=false`.

Seven parser/contract tests pass with `python -m unittest municipio.test_mondariz -v`:
date semantics, missing dates/documents, municipality/identity mismatch, provenance
and date conflicts, complete arrays/pagination changes, failure preserving previous
output, and manifest/disabled licences. A real live extraction through the manifest
and registry wrapper returned **3 records**, with class counts 14:2, 13:1, 18:0.
The shared entity-policy wrapper reports all three as unknown; no classification
or geometry is invented to force publication readiness.

Local uncommitted evidence in `evidence/`: `proyectos.jsonl`, `validation.json`,
inventory/detail JSON responses, municipal and source HTML, UI JavaScript and a
representative normative PDF. The validation includes source URLs, test results,
document counts and coverage limitations. Updates refresh the entire scoped
inventory and atomically replace the output only after successful extraction.
