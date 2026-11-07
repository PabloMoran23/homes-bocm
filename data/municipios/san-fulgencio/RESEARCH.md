# San Fulgencio — Alicante — INE 03118

Verified live 2026-11-07 using the preinstalled Python 3.12 environment at
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Partial municipal planning inventory: two genuine instruments, not a complete
history of development, physical works or granted licences. Scheduling and
coordinate jitter are disabled. `publication_ready` is false: no verified geometry.

## Official current inventory and provenance

- Municipal inventory:
  https://www.sanfulgencio.es/el-ayuntamiento/urbanismo-plan-general/
  The current public page exposes six base-plan PDFs and links labelled
  modifications nº 1 and nº 3. The adapter fetches this page on every run;
  it does not embed a frozen list of records. HTTP 200 with a browser-compatible
  User-Agent; default requests User-Agent sometimes receives HTTP 403.
- Public municipal WordPress page discovery:
  https://www.sanfulgencio.es/wp-json/wp/v2/pages?slug=urbanismo-plan-general
  identifies page 534, published 2016-10-18, modified 2026-04-23. Neither CMS date
  is a plan approval or BOP publication date. API is discovery evidence only;
  the adapter reads the rendered municipal inventory.
- General Plan documents grouped into **one** instrument:
  https://www.sanfulgencio.es/wp-content/uploads/2024/05/Memoria.pdf
  https://www.sanfulgencio.es/wp-content/uploads/2024/05/normativa.pdf
  https://www.sanfulgencio.es/wp-content/uploads/2024/05/ordenanza.pdf
  https://www.sanfulgencio.es/wp-content/uploads/2024/05/Plano.pdf
  https://www.sanfulgencio.es/wp-content/uploads/2024/05/Plano-Orden.pdf
  https://www.sanfulgencio.es/wp-content/uploads/2024/05/impacto-amb.pdf
  The uploads path is not an approval date. Five documents returned PDF/HTTP 200
  in exploratory downloads; Plano-Orden returned 403 with the default User-Agent
  and HTTP 404 in a browser-UA bounded Range probe. The broken link is retained
  exactly as published, with an explicit coverage limitation. Large scanned documents are linked,
  not OCR-parsed. Plano.pdf alone exceeds 1 GB; production extraction does not
  download these base-plan PDFs. They are not evidence of individually built works.
- Modification nº 3:
  https://www.sanfulgencio.es/wp-content/uploads/2021/10/MODIFICACION-PUNTUAL-No-3-PGOU.pdf
  HTTP 200, 512156 bytes. This is a municipal-hosted copy of Alicante BOP nº 50,
  notice 2476/2020, 30 pages. Page 1 expressly identifies San Fulgencio,
  modification nº 3, EXPTE. 04/20, planning reference PL-15/0298; definitive CTU
  agreement **2020-02-04**, BOP publication **2020-03-12**. The operative decision
  says “Aprobar definitivamente”. These dates are distinct from provisional
  approvals in the narrative and from the October 2021 upload directory.
  Page 2 explicitly gives base-plan definitive approval **1998-05-20**; the
  general-plan record retains this documentary provenance. Its publication and
  agreement dates remain null because those events are not separately verified.
  No separate UE-7 or S-8 records are inferred from background narrative.
- Ambiguous link:
  https://www.sanfulgencio.es/wp-content/uploads/2016/10/plan-general.zip
  labelled “Modificacion Puntual Nº 1 PGOU”, HTTP 200. Archive contains 71 entries
  under `plan general/PLANOS_ORD/`, including general-plan sheets and modified
  sheets; the names do not establish a distinct modification nº 1 instrument.
  Excluded from records, link retained in adapter result / validation evidence.
  Archive directory listing saved as `evidence/archive-inventory.json`.
- Other public source discovered:
  https://sanfulgencio.sedelectronica.es/info.0
  The public catalogue lists applications such as Solicitud de Licencia de Obra
  Menor, not a verified register of granted licences. No catalogue item,
  procurement announcement or unrelated municipal news becomes a record.

## Extraction contract and limitations

One current single-page inventory, no observed pagination. The parser requires
all six base-plan document categories, exactly one modification nº 3 PDF, and
reviewed municipal upload URLs. Unexpected links, missing content or pagination
raise an error instead of silently emitting an incomplete inventory. Duplicate
links to the same document are grouped. The ambiguous ZIP is explicitly excluded.

The live adapter downloads the inventory (2 MB bound) and linked modification
notice (4 MB bound), checks the PDF signature, and invokes the **preinstalled**
`pdftotext -layout` executable with a 30-second timeout. No package installation
or dependency changes. Requests use connect/read timeouts of 15/60 seconds.
Parser requires municipality, instrument, operative approval, BOP publication,
CTU agreement and historical base-plan date anchors. Failure leaves prior JSONL
untouched. Update refreshes the same complete partial snapshot; state is not used
as an unverified publication-date filter. No fixed page limit or pagination cut.

No parcel or municipal centroid is substituted for project location. All lat/lon
and geometry fields remain null. Presence in today's municipal inventory is not
an independent certification of consolidated legal validity of all old provisions.
The inventory does not establish full planning, works or licence coverage.

## Validation

- `python -m unittest municipio.test_san_fulgencio -v`: **5 passed**. Tests cover
  document grouping, ambiguous ZIP exclusion, publication/agreement separation,
  PDF line wrapping, missing/wrong content, unexpected pagination/documents,
  manifest loading, disabled licences, repeatable updates and preservation of
  previous output on parsing failure.
- Real `load_portal_adapter(load_manifest('san-fulgencio')).backfill_proyectos`
  invocation: **2 records**, through the repository registry and entity policy.
- `evidence/proyectos.jsonl`: actual live records; `evidence/validation.json`:
  live count, source URLs, excluded document, limitations, source hashes, runtime
  and test result. Source captures: `inventory.html`, `notice.pdf`, `notice.txt`,
  plus discovery and archive-listing evidence. These files remain local.
- Only the four requested source files are added. No shared-source or dependency
  edits; no database, credentials, deployment, publication or git mutation used.
