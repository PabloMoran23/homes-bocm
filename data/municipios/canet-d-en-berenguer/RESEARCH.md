# Canet d'En Berenguer — INE 46082, Valencia

Verified live 2026-11-08 using the preinstalled Python 3.12 virtual environment.
This adapter provides a partial municipal planning snapshot, with four genuine
instruments and 33 document links. It does not provide granted licences or map
geometry. Scheduling and coordinate jitter are disabled; every record has
`publication_ready: false`.

## Official inventories discovered

- https://canetdenberenguer.sedelectronica.es/transparency — anonymous municipal
  transparency tree. The urbanism branch advertises 71 documents, divided into
  planning (30), urban regulations (36), PMUS (4), and interpretation criteria (1).
- https://canetdenberenguer.sedelectronica.es/transparency/2f831604-b93f-4dd3-aff8-67ae2f4b1cd0/
  — urbanism branch, HTTP 200. These numbers describe documents, not projects.
- https://canetdenberenguer.sedelectronica.es/transparency/4f94eb9b-8055-4b3b-8870-f70c995e9c2d/
  — inventory 7.1, HTTP 200. All its five top-level entries are examined.
- https://canetdenberenguer.sedelectronica.es/transparency/0bf8260a-3f45-453a-bc46-f2b86982bb9c/
  — inventory 7.2, HTTP 200, includes PGOU modifications, corrections and Pb2
  norms. Has “Mostrar más”; inspected for discovery but deliberately outside this
  adapter's coverage. No claim to extract this inventory or the complete PGOU.
- https://canetdenberenguer.sedelectronica.es/transparency/581614e3-9da2-408d-964b-7a1d3c17c661/
  — PMUS inventory, HTTP 200, four linked documents.
- https://transparencia.canetdenberenguer.es/ — alternative municipal portal.
  Its urbanism tile points to `#`, not a usable inventory. TLS verification failed
  with both the runtime and system CA bundles; a one-off unverified research
  request captured this public page only. The implemented adapter uses the
  electronic headquarters exclusively, with normal TLS verification enabled.
- https://canetdenberenguer.sedelectronica.es/transparency/dd9e69db-d180-4e8c-91d7-14ffd872b5ee/
  — older Polígono XX link published in the BOP announcement; now HTTP 200 with
  “No se han encontrado elementos”. The current tree supplies the usable folder
  below. The old announcement is not emitted as an extra project.

## Extracted instruments and grouping

1. **Borrador Catálago Bienes y Espacios Protegidos + DIE** (source spelling).
   https://canetdenberenguer.sedelectronica.es/transparency/9e826346-2967-43ac-8e23-60f60aa77cf4/
   Twenty documents, including DIE, memory, protection norms, inventory sheets and
   plans. First response exposes ten; Wicket pagination exposes the other ten.
   These are one draft catalogue record, not twenty projects. No approval claimed.
2. **Convenio urbanístico y proyecto urbanización Polígono XX**.
   https://canetdenberenguer.sedelectronica.es/transparency/57b1c3ec-221c-402a-b33c-81de771a082a/
   Seven documents: agreement, approval decree and a nested project folder with
   five documents (memory/annexes, plans, specifications, budget, ESS).
   Nested folder:
   https://canetdenberenguer.sedelectronica.es/transparency/2684a08a-a53a-49a6-8c4f-585b184ba95c/
   `fecha_aprob: 2026-03-02` comes specifically from the inventory label
   “DECRETO 2026-0515 [Aprobación Proyecto de Urbanización Polígono XX) 02/03/2026”.
   The document label is the evidence boundary; decree contents are not parsed.
3. **Proyecto urbanización Polígono XIII**.
   https://canetdenberenguer.sedelectronica.es/preview-document/05b68759-539f-40b0-a4bc-366a3875fe33
   One project plus its separately listed “CONVENIO 2022-0008 [CONVENIO CESIÓN
   POLÍGONO XIII]” retained under the same record. No inferred approval date.
4. **Plan de Movilidad Urbana Sostenible (PMUS)**. Four documents in the PMUS
   folder: DIE, environmental-report announcement, definitive-version document
   and plenary agreement certificate. `fecha_acuerdo: 2026-06-19` comes from
   “Certificado de acuerdo Pleno 19 junio 2026”; this does not assert the legal
   nature of the agreement or a plan approval. `fecha_aprob` remains null.

The remaining 7.1 entry, an Abanca agreement concerning Joanot Martorell 4, is
excluded because its label alone does not establish a physical project. All
33 extracted links are the actual public `preview-document` URLs, with original
labels and the containing inventory URL in `documentos[].source_url`. These are
preview links, not asserted direct PDF download URLs. PDF content and legal
validity have not been independently assessed.

## Crawl and semantics

The adapter follows public Wicket navigation actions via GET, never evaluates
JavaScript, and reads only XML component CDATA for load-more results. No account
or authentication bypass is used. It traverses nested folders, checks advertised
recursive document counts, detects duplicate documents and pagination loops, and
fails on changed/unreviewed planning folders, incomplete pages or unsupported
root pagination. A response limit, timeout and depth/page guards fail explicitly
rather than silently truncate. Updates refresh the same complete scoped snapshot;
output is replaced atomically after extraction succeeds.

Generic `fecha` and `fecha_publicacion` are null. The 2024 DOGV announcement in
PMUS concerns an environmental report and is retained as a document label, never
used as publication/approval of the PMUS itself. Crawl dates, document names with
years, agreement identifiers and the page clock do not become event dates.
Coordinates and geometry remain null: no municipal centroid, random jitter or
unverified position is substituted.

## Validation and local evidence

Run from the repository root:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_canet_d_en_berenguer -v
```

Six tests passed: XML document links; recursive grouping and complete pagination;
missing advertised documents; pagination without progress; preservation of an
existing snapshot on source failure; and manifest/disabled-licence contract.
The mocked grouping test separately verifies approval, agreement, publication and
missing-coordinate semantics.

A real `CanetDEnBerenguerAyuntamientoAdapter.backfill_proyectos` call completed
with normal TLS verification, four records and 33 distinct document links.
Local, uncommitted evidence: `evidence/proyectos.jsonl`,
`evidence/validation.json`, and the six extraction responses under
`evidence/captures/`. The validation file includes live source URLs, capture
hashes, counts and limitations. Additional discovery captures are also local.
No shared source files, dependencies, database or deployment systems were changed.
