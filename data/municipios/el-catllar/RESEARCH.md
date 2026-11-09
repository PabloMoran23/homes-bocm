# El Catllar — INE 43043, Tarragona

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Implemented one municipal adapter. Coverage is a **partial municipal planning
inventory**, not a complete inventory of current planning, public works or granted
licences. Scheduled ingestion and missing-coordinate jitter are disabled.

## Official source discovery

- https://www.elcatllar.cat/ — current municipal website. Its Urbanisme link
  points to
  https://www.seu-e.cat/web/elcatllar/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
  (HTTP 200). The site also links to the municipal transparency portal and
  electronic headquarters. Navigation and application forms are not records.
- Extraction inventory:
  https://seu-e.cat/ca/web/elcatllar/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200. The municipal table contains five populated planning rows and one
  blank row. Its content block reports `Actualització: 20/02/2023 | Font: Propi ens`;
  another block has a 2019 update. Neither timestamp is a project date.
- The inventory links directly to Generalitat RPUC dossiers. A sampled live
  request to dossier 285254 returned HTTP 200 with a JavaScript application shell.
  The adapter retains every row's document/reference links but does not claim to
  have downloaded the dossier documents or extracted RPUC geometry.
- The candidate technical-project path
  https://seu-e.cat/ca/web/elcatllar/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-tecnics-221
  returned HTTP 404. It supplies no records.
- Discovery also found the provincial public CIDO planning index:
  https://cido.diba.cat/normativa_local/7681631/planejament-urbanistic-ajuntament-del-catllar
  with notices referring to later modifications than those in the municipal
  table. This establishes a coverage limitation; those notice summaries are not
  merged into this inventory or treated as projects without dossier inspection.
  Procurement results were excluded from extraction.

## Extracted instruments and date semantics

All links below are source-provided RPUC references. One instrument corresponds to
one dossier. Modification numbers 1 and 2 are one municipal row and one dossier,
so they remain one record. Multiple documents for the same dossier are grouped
in `documentos`; conflicting duplicate metadata fails extraction.

| Dossier | Municipal subject | Approval column | Publication column |
| --- | --- | --- | --- |
| [285254](https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/285254) | POUM modification 8, La Fàbrica | 2020-06-05 | 2021-04-30 |
| [263041](https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/263041) | POUM modification 4, restaurant use | 2013-04-04 | 2013-07-04 |
| [261599](https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/261599) | POUM modification 3, subclau 24 | 2013-04-04 | 2013-06-20 |
| [254038](https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/254038) | POUM modifications 1 and 2 | 2010-10-28 | 2011-01-17 |
| [242676](https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/242676/documents) | Municipal POUM | 2009-04-22 | 2010-02-09 |

`fecha_aprob` and `fecha_publicacion` come from separate explicitly labelled
columns. `fecha`, `fecha_acuerdo` and `fase` remain null: the table does not identify
an agreement date separately or a specific approval stage. Blank dates remain
null and malformed dates fail. The source classifies four POUM modifications as
`Pla director urbanístic`; this value is retained as `instrumento_fuente`, not
silently corrected or used as the normalized type. Municipal expediente numbers
are retained where supplied; RPUC IDs are stored separately. The POUM row does not
supply an expediente number or instrument classification.

Every document has its exact linked URL, link label, provenance inventory URL
and a reference type. RPUC dossier references are not represented as PDF files.
No geometry is verified: lat/lon/geometry remain null and publication_ready is
false. No municipal centroid or approximate point is substituted.

## Extraction behavior and validation

One bounded live HTML request (connect/read timeouts 10/40 seconds, maximum
4 MB) refreshes the entire inventory on both backfill and update. It validates
the municipal page title and all eleven column headings. The live page embeds
all rows; DataTables only sorts, filters and paginates these rows in the browser,
with no AJAX or server-side configuration. The parser reads every embedded row,
including rows beyond the default browser page size. Detected remote pagination
or a next-page link fails explicitly instead of returning partial results.

The live HTML omits closing row tags. Direct-cell parsing prevents nested rows
from contaminating the first record's dates and documents. A blank row is ignored;
nonempty malformed rows, missing/ambiguous dossiers, unsupported titles and
conflicting duplicate instruments fail before output replacement. IDs use the
stable RPUC dossier identifier. No output count cap truncates the inventory.

- `python -m unittest municipio.test_el_catllar -v`: six tests passed. Tests cover
  distinct date semantics, null fields, document grouping, malformed live row
  endings, 25 embedded rows, invalid sources/dates, pagination rejection, update
  behavior, manifest loading and disabled licences.
- Live extraction through `load_portal_adapter(load_manifest('el-catllar'))`:
  **5 actual records**, status ok; shared entity-policy annotation status ok.
- Evidence in the job-local `evidence/`: `proyectos.jsonl`, `validation.json`,
  `planejament.html`, `normativa-urbanisme.html`, `projectes-tecnics.html` (404),
  and `rpuc-shell.html`. Evidence is local and is not source code to commit.

No credentials, other workspaces, database, deployment, publication, GitHub,
package installation or git mutation was used.
