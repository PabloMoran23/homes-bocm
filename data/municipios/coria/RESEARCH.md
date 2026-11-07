# Coria — Cáceres — INE 10067

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Official inventories investigated

- https://coria.org/ayuntamiento/index.php/plan-general-municipal-y-pepch/
  returned HTTP 200. This is the dedicated municipal document inventory for the
  new PGM and revision of the special plan for the historic centre (PECH/PEPCH).
  Its Documentación section contains three participation presentations and seven
  advance-document entries. All ten entries are retained, not ten projects.
  One is the PECH document; the other nine belong to the PGM dossier. The page
  labels the advance December 2025; this is not an approval or publication date.
  Neither a pagination control nor a next-page link was present.
- https://transparencia.coria.org/transparencia/urbanismo returned HTTP 200.
  This broader current inventory links NNSS, the existing historic-centre plan,
  Los Rosales partial plan and related documents, and modification 29 of NNSS
  (expediente 1987/2023). It also includes an unrelated feline-management plan
  and an information-access resolution. This inventory was captured for research;
  it is outside the implemented two-instrument snapshot. Its navigation links
  are not treated as individual projects and its document-title dates are not
  interpreted as agreement dates.
- https://doe.juntaex.es/otrosFormatos/html.php?anio=2026&doe=440o&xml=2026080310
  returned HTTP 200. The notice explicitly identifies Coria's PGM advance and
  initial strategic document. It provides the initial approval of the **advance**
  at the plenary session of **2026-01-21**, and DOE publication **2026-03-05**.
  The notice's own date, 2026-02-19, is neither of those dates. The adapter parses
  agreement and publication separately and links their provenance. It does not
  assert final approval of the PGM or apply those dates to the PECH.
- https://doe.juntaex.es/pdfs/doe/2026/440o/26080310.pdf is the authentic-format
  PDF linked by the DOE HTML. It returned HTTP 200 with a PDF signature and is
  captured locally. Date parsing uses the DOE HTML transcription, which warns
  that the PDF is the authentic version.

## Implemented scope and semantics

`CoriaAyuntamientoAdapter` implements the four portal methods. Backfill and
update refresh the complete dedicated inventory, without time filtering or a
record limit. One record groups the PGM documents and DOE reference; a second
groups the PECH revision document. Identity is stable per instrument/revision,
independent of PDF filenames. Every document retains its title, URL and inventory
provenance. Publisher-supplied sizes and hashes are retained as source text, not
reported as verified checksums. URL spaces are encoded.

The source has a discrepancy: “06 Documento Inicial Estratégico” and “06 Memoria
de Participación Ciudadana” link to the same DIE PDF but have different displayed
sizes and hashes. Both entries and their distinct metadata are preserved. The
adapter does not guess a corrected URL or create another project for this alias.

The parser requires the planning-page title, documentation section, advance
label, and named PGM and PECH technical documents. It rejects newly detected
pagination rather than silently returning page one. Missing/changed DOE identity
or date structure, unexpected document hosts, HTTP errors, redirects to a
different host, and responses over 2 MB abort extraction. Both source encodings
are handled (municipal UTF-8 and DOE Latin-1). Requests have a 40-second timeout.

Coverage is deliberately partial: no NNSS history, other modifications, municipal
works inventory, or granted-licence register. No news, procurement announcement,
application form, participation form or unrelated management plan becomes a
record. The actual planning documents establish the two instruments.

No PDF plans were digitized into geometry. Coordinates and geometry are null;
no municipality centroid or random offset is substituted. `publication_ready`
is false. Schedule, missing-coordinate jitter and licences are disabled in the
manifest. The PGM's generic date and final approval date remain null; PECH dates
remain null because a specific agreement was not established.

## Validation and local evidence

Run parser and integration-contract tests:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_coria -v
```

Seven tests cover grouping and duplicate-link metadata, distinct date semantics,
missing coordinates, rejection of changed/unrelated sources, pagination detection,
all-link retention, stable identities, refresh/disabled licences and manifest
loading through the registry.

A real registry-loaded `backfill_proyectos` fetched both sources, using runtime
config `capture_dir=evidence`. It produced **2 actual planning records**, with
**11 document entries** (10 inventory entries plus the DOE PDF). The existing
entity-policy wrapper ran successfully; both entity categories remain unknown.
This is not a claim of map or publication readiness.

Local, uncommitted evidence: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/pgm.html`, `evidence/doe.html`, `evidence/doe.pdf`, and the researched
`evidence/urbanismo.html`. Validation records source URLs, count, limitations,
test result, extraction timestamp and SHA-256 hashes of captures. No credentials,
databases, deployment, publication, dependency or shared-source changes were used.
