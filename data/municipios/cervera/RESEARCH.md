# Cervera — Lleida — INE 25072

Verified live 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The adapter extracts **five real planning instruments from six municipal edicts**.
Coverage is deliberately partial; neither completeness nor current legal validity
is asserted. Scheduling and licence extraction are disabled. No verified geometry
is available and every record has `publication_ready: false`.

## Source discovery and provenance

- [Current municipal website](https://cervera.cat/) returns HTTP 200 and links
  to the Territori section. The former `https://www.cerverapaeria.cat/` returns
  HTTP 410. The current Territori HTML returned HTTP 403 during discovery.
- The public WordPress pages endpoint
  `https://cervera.cat/wp-json/wp/v2/pages?search=territori` returned HTTP 200.
  Page 1210 (Territori) links to the municipal transparency planning page.
  This discovery response was inspected, not used to manufacture project rows.
- [Municipal planning inventory](https://seu-e.cat/ca/web/cervera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic)
  returns HTTP 200 but only general MUC/RPUC links, without specific plan files.
  Its 2023-02-10 update timestamp is not an instrument approval/publication date.
- [Municipal licence inventory](https://seu-e.cat/es/web/cervera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/llicencies-d-obres-menors-majors-i-activitats-178)
  is discoverable with annual attachments through 2024. No individual granted
  licences were extracted; this adapter is expressly limited to planning.
- [CIDO planning inventory for Ajuntament de Cervera](https://cido.diba.cat/normativa_local/8349590/planejament-urbanistic-ajuntament-de-cervera)
  is the usable official inventory, maintained by Diputació de Barcelona.
  Live HTML exposes **35 notices in one table without pagination**. Six link to
  modern BOP Lleida PDF files. The other **29 legacy BOP/DOGC notices are counted
  and explicitly excluded**, not silently lost as pagination or a record limit.
  The selection is based on original-document URL format, not a hardcoded list
  of records or a recent-date cutoff. Additional modern BOP entries are discovered
  from the full table on each run. A pagination control fails the extraction and
  requires crawler review.
- The six originals are municipal edicts hosted by Diputació de Lleida, not
  procurement announcements or forms. Each supplies municipal identity,
  a bulletin publication date and an operative planning approval. These are
  genuine planning instruments; the edicts are supporting documents for those
  instruments. `source=ayuntamiento` describes the author, while
  `origen=edicto_municipal_bopl_via_cido` identifies the actual discovery chain.
- [Official Idescat municipality codes](https://www.idescat.net/codis/?id=50&lang=en&n=9)
  identifies Cervera as 250729 (municipal code with check digit); the five-digit
  INE code is 25072. Lleida province is 25. Cadastral/NIF identifiers appearing
  in PDFs are not substituted for INE.

## Extracted instruments and original evidence

| Instrument | Publication | Agreement | Operative stage | Original |
| --- | --- | --- | --- | --- |
| Waste-deposit extension, initial notice | 2024-06-12 | 2024-05-15 | Initial | [BOP 114, edict 4918](https://ebop.diputaciolleida.cat/aplicacions/bop/bopV1/fitxers/pdf/2024/114/202411404918.pdf) |
| Same waste-deposit instrument, subsequent notice | 2025-03-19 | 2025-02-20 | Provisional | [BOP 54, edict 2260](https://ebop.diputaciolleida.cat/aplicacions/bop/bopV1/fitxers/pdf/2025/54/20255402260.pdf) |
| PEU Agropecuari Explotació Porcina Dallarucu SL | 2025-04-07 | 2025-03-27 | Initial | [BOP 67, edict 2863](https://ebop.diputaciolleida.cat/aplicacions/bop/bopV1/fitxers/pdf/2025/67/20256702863.pdf) |
| POUM modification for Refugi Segarra extension | 2025-12-11 | 2025-07-31 | Initial | [BOP 236, edict 10191](https://ebop.diputaciolleida.cat/aplicacions/bop/bopV1/fitxers/pdf/2025/236/2025236010191.pdf) |
| Pla parcial, industrial sector SUD Mobel Línea | 2026-02-10 | 2025-10-23 | Initial | [BOP 27, edict 1021](https://ebop.diputaciolleida.cat/aplicacions/bop/bopV1/fitxers/pdf/2026/27/20262701021.pdf) |
| Pla de millora urbana, Cases Noves 10 | 2026-02-12 | 2025-09-04 | Initial | [BOP 29, edict 1096](https://ebop.diputaciolleida.cat/aplicacions/bop/bopV1/fitxers/pdf/2026/29/20262901096.pdf) |

The two waste-deposit edicts explicitly describe the same extension, despite the
initial CIDO row's generic title. They form one record with both document URLs,
publication dates, agreement dates and phases retained in `documentos`.

**Source discrepancy:** CIDO labels the 2025-03-19 waste-deposit notice definitive;
the original says provisional and explicitly refers definitive approval to the
territorial commission. The adapter uses the original's provisional phase and
retains CIDO's label as `fase_inventario` for audit. References to eventual
approval are not parsed as operative approval. News reporting later actions is
not used to update the extracted edicts' historical stages.

## Semantics, limits and operation

`fecha_publicacion` comes from the inventory's publication column and is checked
against the original PDF header. `fecha_acuerdo` and `fecha_aprob` come only from
explicit agreement/session language; signature dates are not used. Generic
`fecha` stays null. Missing agreement dates stay null. Unknown/multiple operative
phases, wrong municipality, conflicting dates, changed inventory layout, HTML
instead of PDF and failed downloads raise errors before replacing the snapshot.

The top-level phase/date refer to the most recently published **covered** notice,
not an assertion of the present legal state. Legacy notices, DOGC amendments,
other inventories, technical plan annexes and unindexed later decisions remain
outside coverage. All links in the selected notice are represented by its original
BOP PDF; full edict text and source titles remain attached. Documents are grouped
by normalized instrument title, with a content-based rule for the verified
deposit extension. New differently worded descriptions may need further identity
review; this is not a general cross-register entity resolver.

The live adapter makes one full-inventory request plus one request per selected
PDF (seven requests in this run), with connection/read timeouts and an 8 MB
response guard. It uses the existing `requests`, BeautifulSoup and preinstalled
`/usr/bin/pdftotext`; no dependencies or software were installed. PDF conversion
has a 30-second timeout. Both backfill and update refresh the complete scoped
snapshot; update does not claim incremental history. Licence methods return an
empty disabled result. No municipal centroid, parcel coordinate or random jitter
is substituted for absent project geometry.

## Validation and local evidence

- `.../venv/bin/python -m unittest municipio.test_cervera -v`: **7 tests passed**.
  Cases cover date semantics, correction of the misleading inventory phase,
  preservation/grouping of edicts, missing dates, numeric agreement dates,
  pagination/invalid sources, fail-before-replace behavior and manifest loading.
- Real extraction through `load_portal_adapter(load_manifest('cervera'))`:
  `status=ok`, **5 records**, **6 PDFs**, **29 excluded notices**.
- `evidence/proyectos.jsonl`: actual output through the registry adapter wrapper.
- `evidence/validation.json`: live count, source URLs, limitations and test result.
- `evidence/sources/`: exact live inventory, original PDFs and extracted PDF text.
  Other discovery responses/captures are also under `evidence/`.
- These evidence files are local and ignored by git; only the four requested
  source files were added. No shared code, dependencies, git internals, credentials,
  databases, deployment or publishing operations were modified or invoked.
