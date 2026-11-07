# Pallejà — INE 08157, Barcelona

Verified 2026-11-07 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The adapter implements a **partial current public-works snapshot**, not a historical
archive, complete planning register or granted-licence inventory. Scheduling,
licences and missing-coordinate jitter are disabled. No coordinates are inferred.

## Official source discovery

- https://www.palleja.cat/ — municipal homepage explicitly links “Anuncis / Edictes”
  to https://palleja.eadministracio.cat/board/ and “Transparència” to the same
  municipal electronic seat. HTTP 200, captured in `evidence/home.html`.
- https://palleja.eadministracio.cat/board/ — **implemented source**, HTTP 200.
  Anonymous notice table exposes document title, municipal expediente, procedure,
  description, publication date and stable `/preview-document/<UUID>` links.
  “Veure'n més” loads additional rows through public Wicket AJAX requests in the
  same anonymous session. This is ordinary public navigation, without login.
- https://palleja.eadministracio.cat/transparency — HTTP 200; root advertises
  “7. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT” (14 documents) and “9. EXPEDIENTS
  EN EXPOSICIÓ PÚBLICA” (40 documents). Those category counts are **not** the board
  count and their contents are not claimed as extracted. Dynamic category
  navigation was not resolved in this implementation.
- https://seu-e.cat/ca/web/palleja/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200. Links RPUC with `municipiSel=08157`, confirming municipality-specific
  provenance, and MUC with `municipi=08157`. It does not itself expose plan records.
- https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08157
  — redirects to
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cercaPublic?reqCode=cerca&municipiSel=08157
  and returns the JavaScript application shell, not a parsed inventory. No RPUC
  instruments or geometries are invented from that shell.
- https://www.palleja.cat/ajuntament/plans-protocols-i-altres — HTTP 200; mixed
  policy/strategic-plan index (health, equality, environment, mobility), excluded
  from the physical-works extraction. Likewise the municipal “Actuacions i
  campanyes” index contains events/training/campaigns rather than a works register.
- Licence application forms and the board's environmental-licence public
  information notice are not evidence of a granted licence. Procurement notices,
  staff recruitment, budget modifications and meeting agendas are excluded.

## Live inventory and grouping

The complete active board contained **28 document announcements over three
pages** (10 + 10 + 8). The final AJAX response replaces the load-more component
with its hidden placeholder. All pages are fetched before selecting works. Ten
qualifying documents form **five municipal expedientes**, with two document links
retained per record:

| Expediente | Physical work | Board publication |
| --- | --- | --- |
| 3455/2026 | Circuit pumptrack | 2026-11-02 |
| 3501/2026 | Painting and road signage, eastern public-road area | 2026-10-28 |
| 3575/2026 | Renewal and energy efficiency of Fontpineda public lighting | 2026-10-19 |
| 3377/2026 | Pavement repair, east/west Ronda Santa Eulàlia | 2026-10-01 |
| 3135/2026 | Asphalting carrer Pau Claris | 2026-09-25 |

The adapter selects technical projects/memories under `Actuacions Urbanístiques`
with explicit physical-work terminology, conservatively excluding procurement.
The supported vocabulary is partial; other procedures and types of instruments
are outside this adapter's coverage. Records are grouped by actual expediente,
not by PDF, title similarity or date. The ID depends on expediente and remains
stable when document order changes. The titles/descriptions retain the board's
wording; obvious source spelling errors are not silently rewritten.

Each of the ten stable preview pages was fetched live and checked for its named
document and PDF viewer. The technical memory for pumptrack was also downloaded
manually in an anonymous session:
https://palleja.eadministracio.cat/preview-document/467d6084-4773-4ea5-bab2-0517b2bce227
(`evidence/pumptrack.pdf`, 62 pages). Its cover identifies a real circuit between
Avinguda de l'Onze de Setembre and Ronda Santa Eulàlia in Pallejà, not a generic
licence form. Preview PDF URLs are session-dependent: a URL reused in another
session returned 403; a fresh anonymous preview and PDF request in one session
returned HTTP 200. Stable preview URLs, not transient viewer tokens, are retained
as document provenance.

## Dates, completeness and geometry

`fecha_publicacion` comes only from the board's “Data de Publicació” column; at
record level it is the earliest attached notice visible in this snapshot. Every
document also retains its own publication date. It is not asserted to be the
first-ever publication of that instrument. The explicitly stated initial approval
is retained as `fase`, but **no agreement or approval date is inferred** from a
publication date, signature date, document-creation date, plan horizon or crawl
time. `fecha`, `fecha_acuerdo`, `fecha_aprob`, `lat`, `lon` and `geometry` are null.
The PDF bodies are not automatically parsed for dates or geometry. There is no
verified project geometry, so `publication_ready` is false.

Update refreshes the entire active-board snapshot and does not use a historical
cursor. Notices can expire; neither backfill nor update claims historical
completeness. Unknown pagination markup, session redirects, missing controls,
repeated pages, missing provenance, invalid dates, absent PDF viewers, response
sizes above 5 MB or more than 100 pages raise errors instead of writing a truncated
result. The adapter writes its JSONL atomically only after the complete crawl and
document checks succeed. No shared source files or dependencies were changed.

## Reproducible validation and local evidence

- `python -m unittest municipio.test_palleja -v`: six tests passed, covering grouped
  documents, stable identity, publication/approval separation, missing geometry,
  exclusion of non-project content, provenance/date failures and AJAX terminal
  controls including the hidden Wicket placeholder.
- `PallejaAyuntamientoAdapter(...).backfill_proyectos(Path('evidence/proyectos.jsonl'))`
  with `config.evidence_dir='evidence'`: five actual projects, 28 board documents,
  three pages, ten verified document previews.
- Manifest was loaded with `municipio.manifest.load_manifest('palleja')`; no registry
  edits are needed because the manifest declares the adapter's import path.
- `evidence/validation.json` records `live_records`, `source_urls`, limitations,
  page/document counts and SHA-256 hashes of live captures. `live-board-0.html`,
  `live-board-1.xml`, `live-board-2.xml` and `live-document-*.html` preserve actual
  fetched responses. Discovery captures and pumptrack PDF/text are also local.
- Evidence is local and outside the four source files for review; no publishing,
  deployment, database, credentials, repository mutation or installation used.
