# Sineu — INE 07060, Illes Balears

Verified 2026-11-09 using live anonymous HTTPS requests. This adapter covers the
municipal **Urbanisme document inventory**, not all municipal construction
activity. It emits three genuine planning/rehabilitation bundles with four
linked PDF documents. Scheduling, licences and coordinate jitter are disabled.
No credentials or authenticated sources were used.

## Official sources discovered

- [Municipal documents root](https://ajsineu.net/ca/arxius-i-documents/tramits-i-documents)
  lists Urbanisme (5 documents), Exposició Pública (2 documents), heritage
  catalogues, minutes, forms and other unrelated categories.
- [Urbanisme](https://ajsineu.net/ca/archivos-y-documentos/urbanisme): HTTP 200,
  five named document cards, no pagination in the observed HTML. Four cards
  describe real instruments; one is procedural guidance and is excluded.
- [Exposició Pública](https://ajsineu.net/ca/arxius-i-documents/exposicio-publica)
  lists activity notices for c/ Ciutat / Xaloc and Plaça Es Fossar, 13. These are
  outside this adapter's reviewed inventory and are not treated as granted
  building licences.
- [Heritage catalogues](https://ajsineu.net/ca/arxius-i-documents/catalegs-de-patrimoni-historic)
  has 2014 and 2010 folders. These are a separate inventory, not crawled here.
  Coverage is explicitly partial.

## Included instruments and provenance

1. [Normes subsidiàries de Sineu](https://ajsineu.net/ca/arxius-i-documents/urbanisme/normes-subsidiaries-de-sineu):
   [official PDF](https://ajsineu.net/sites/cilma_sineu/files/2020-09/archivo_doc316572.pdf),
   13,198,039 bytes during research. Scanned text refós of the municipal NNSS;
   first page visually checked in `evidence/nnss-first-page.png`. Its BOCAIB
   header is 31 January 1991. The introductory paragraph distinguishes the
   original planning approval from subsequent amendments. No OCR or document
   date parser is implemented, so these dates are not emitted as structured
   project dates.
2. [Modificacions i adaptació normes subsidiàries de Sineu](https://ajsineu.net/ca/arxius-i-documents/urbanisme/modificacions-i-adaptacio-normes-subsidiaries-de-sineu):
   [official PDF](https://ajsineu.net/sites/cilma_sineu/files/2020-09/archivo_doc37434.pdf),
   87,158 bytes. Text extraction confirms a BOIB extract, number 78,
   **publication 1 June 2006**, carrying the Consell de Mallorca **agreement of
   3 April 2006**. It definitively approves the urban-soil provisions **partially**,
   with prescriptions, while suspending approval of rural-soil provisions.
   This is a distinct adaptation/amendment instrument, not evidence of full
   definitive approval. Runtime does not parse the PDF body: both structured
   publication and agreement dates, and phase, remain null rather than applying
   the portal's 2020 upload date or asserting complete approval.
3. [Programa área rehabilitación integral del casco antiguo del municipio rural de Sineu](https://ajsineu.net/ca/arxius-i-documents/urbanisme/programa-area-rehabilitacion-integral-del-casco-antiguo-del-municipio):
   [memory/programme PDF](https://ajsineu.net/sites/cilma_sineu/files/2020-09/archivo_doc298327.pdf),
   2,277,872 bytes. Its title identifies period 2015–2017, and its opening text
   describes submission for declaration of the rehabilitation area and adaptation
   to RD 233/2013. It references earlier area agreements of 2002 and 2007;
   these are not approval dates for this programme. Grouped with
   [Delimitación ARI nucleo històrico Sineu](https://ajsineu.net/ca/arxius-i-documents/urbanisme/delimitacion-ari-nucleo-historico-sineu)
   and its [boundary PDF](https://ajsineu.net/sites/cilma_sineu/files/2020-09/archivo_doc298328.pdf),
   2,721,228 bytes. The memory explicitly describes the attached area plan.
   The boundary is supporting documentation, not a separate project. All four
   attachment links and their detail-page provenance are retained across the
   three records.

The four detail pages show **08/09/2020 beside their file metadata**. This is
stored as `documentos[].fecha_fichero_portal`, with no claim that it is an act's
publication date, approval date or adoption date. `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, `fecha_aprob` and `fase` remain null in the project records.

## Excluded material and limits

[Tramitacions xarxes de distribució](https://ajsineu.net/ca/arxius-i-documents/urbanisme/tramitacions-xarxes-de-distribucio)
links a 2025 procedural guide describing submissions, technical reports and
network-work authorisations. Its actual PDF was fetched and text-inspected;
it is not a named project, physical work or granted licence. It is explicitly
excluded and reported in extraction statistics. No procurement or unrelated
news records are ingested.

An available historical document does not establish present legal validity or
execution. No comprehensive bulletin history, public-works inventory, planning
register, granted-licence register or GIS geometry is claimed. Maps embedded in
PDFs are not extracted into georeferenced geometries; all geometry and coordinate
fields remain null, `publication_ready` is false. The shared entity policy marks
all three records `pendiente` / `insufficient_identity_evidence`: these document
bundles do not supply the expediente identity needed for activity eligibility.
This annotation is retained, not bypassed.

## Implementation and validation

The scraper fetches the live index, follows each included detail card, verifies
its title and advertised attachment count, then downloads each attached PDF.
It checks HTTP status, final official host, response bounds and PDF signature,
and records each PDF's SHA-256. Detail/card conflicts, unknown new entries,
missing documents and changed markup fail visibly. Pagination controls or
`page=` links also fail visibly: no first-page-only success is possible.
The current inventory is unpaginated. The reviewed card identities group the
ARI documents; stable IDs do not depend on ordering, dates or crawl time.
Backfill and update both refresh the complete reviewed snapshot; output is
replaced only after every source succeeds. Licence methods return disabled
with an empty output.

Executed with the preinstalled runtime:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sineu -v
```

Seven tests passed: grouping and exclusions; date semantics; pagination;
unknown/login/empty pages; missing or inconsistent attachments and external
links; complete refresh and preservation of output on failure; manifest and
disabled licences. A live run loaded the manifest through the shared adapter
registry and called `backfill_proyectos`: **3 records, 4 verified PDFs, 5 index
entries, 1 explicit exclusion**. Registry entity-policy annotations were applied.

Local, uncommitted evidence: `evidence/proyectos.jsonl`,
`evidence/validation.json`, original detail HTML/PDF/text captures and
`evidence/live_sources/` (URL-hashed HTML/PDF captures from the actual adapter
run). Validation includes live record count, exact source URLs, limitations,
test result and entity-policy outcome. No shared source or dependency changes.
