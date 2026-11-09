# El Pont de Vilomara i Rocafort — Barcelona — INE 08182

Verified live 2026-11-09. Exactly one municipal adapter, using the public RPUC
register linked by the municipal transparency portal. This is a partial planning
inventory, not a complete works inventory or a register of granted licences.
No authentication, credentials, database, deployment or publication operations.

## Discovery and official current inventories

- Municipal urbanism service:
  https://www.elpont.cat/serveis-i-tramits/tramits-i-gestions/urbanisme-i-obres.html
  (HTTP 200; capture `evidence/urbanisme.html`). Its attached licence,
  communication and occupation files are application forms, not granted licences.
  They are excluded. The page links urbanism transparency and the RPUC.
- Municipal plans inventory:
  https://www.elpont.cat/ajuntament/plans-campanyes-i-projectes
  (HTTP 200; `evidence/inventory-0.html`). Four entries at inspection: youth plan,
  LGTBI+ policy plan, DUPROCIM and forest-fire prevention plan 2020–2025. This
  inventory does not provide the urban-planning/public-works coverage used here;
  none of those entries is emitted by this adapter.
- Urbanism transparency inventory:
  https://seu-e.cat/ca/web/elpontdevilomarairocafort/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
  (HTTP 200; `evidence/inventory-2.html`). Links planning, regulations, geographic
  information and territorial plans.
- Municipal planning transparency:
  https://seu-e.cat/ca/web/elpontdevilomarairocafort/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  (HTTP 200; `evidence/inventory-1.html`). Explicitly links the municipality filter:
  https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08182
  and MUC. Its page update of 2025-09-29 is not an instrument date.
- That official RPUC legacy link redirects to
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/index.html#/consulta/cercaPublic?reqCode=cerca&municipiSel=08182
  (`evidence/rpuc.html`). HTML is an Angular shell. The public application's
  `ConsultesService` exposes anonymous GET endpoints under
  `https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/`.
  The downloaded public JS is retained in evidence. Only public consultation
  endpoints are used; no authentication or private APIs are accessed.

## Extraction and provenance

`basica?municipi=08182&idioma=ca&firstRecord=1&rpp=10&sortColumn=data&sortDirection=asc`
returns `totals: 29`. Live requests for pages 1, 2 and 3 returned 10, 10 and 9
unique dossiers. Despite its name, `firstRecord` is a one-based page number,
not a row offset: separate five-row probes verified pages 1, 2, 3, 4, 5, 6;
0 aliases 1. The adapter iterates to the declared total and rejects changed
totals, empty/short intermediate pages and duplicate IDs. It does not silently
truncate results. Output is replaced only after all selected details parse.

The 29 associated entries include 11 regional/territorial instruments with other
lead municipalities (e.g. Solsona, Manresa, Barcelona and Súria). Those are
explicitly excluded. All 18 entries whose `municipi` is exactly
`El Pont de Vilomara i Rocafort` are fetched through `detall`, and their returned
municipality and dossier ID are checked. The selected set includes the general
plan revision, its modifications, consolidated regulations, partial plans and a
urban improvement plan. Historic entries are retained; no claim is made that
these constitute a new approval, construction in progress, or a complete set of
currently effective regulations.

One record per RPUC dossier; all 140 document metadata entries are grouped under
those 18 instruments. IDs derive from actual RPUC dossier IDs; `expediente` is the
source's `numComplet`. Document titles and IDs come from `documents`. Download
links use the public application's verified `documents?documentId=...&downloadType=inline&idioma=ca`
route, not guessed file paths. A live request for document 161131 returned HTTP
200, `application/pdf`, and PDF bytes (`evidence/83044-approval.pdf`). Other PDFs
are linked with source metadata but have not all been downloaded or independently
reviewed. `url_fuente` retains each detail API URL, `url` its human viewer, and
`inventario_url` the municipal provenance page.

Dates come exclusively from `dataAprovacio` and `dataPublicacio` in each detail.
For example, dossier 83044, Revisió del Pla general d'ordenació, explicitly gives
approval 1998-07-21 and publication 1998-09-28. The inventory `data` field and
registration-seat dates are not substituted. Generic `fecha`, `fecha_acuerdo`
and `fase` remain null: a date alone does not establish an approval stage.
Missing dates remain null. Inventory `vigencia` and `registrat` are retained as
source flags, without inferring a blanket legal status from them.

No verified vector geometry or project coordinates were extracted. `lat`, `lon`
and `geometry` are null, `publication_ready` is false. There is no invented
municipal-centroid substitute. `schedule.enabled`, `geocode.jitter_missing` and
`licencias.enabled` are false. Updates refresh the complete selected snapshot;
no state timestamp is used as an approval/publication date.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_el_pont_de_vilomara_i_rocafort`: 6 tests passed.
  Tests cover distinct/missing dates, grouped documents, identity validation,
  full pagination, regional exclusions, pagination failures preserving previous
  output, and manifest/registry loading.
- Live `load_manifest` → `load_portal_adapter` → `backfill_proyectos`:
  18 actual records, 29 inventory entries inspected, 11 excluded, 140 documents.
- Shared entity-policy annotation reports status `ok`; 9/18 classifications are
  unknown. No local category override or shared policy change was introduced.
- `evidence/proyectos.jsonl`: actual annotated adapter output.
- `evidence/validation.json`: timestamp, live count, requested source URLs,
  extraction result, test result and explicit coverage/geometry limitations.
- `evidence/rpuc-basica-{1,2,3}.json` and `evidence/rpuc-detall-*.json`:
  live raw inventory/detail responses, plus discovery captures and the sample PDF.

Evidence is local and must not be committed. Only the manifest, this research
file, the municipal adapter and its parser tests are source additions.
