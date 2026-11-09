# Castelló — Valencia — INE 46257

Live verification: 2026-11-09. Implemented one deliberately narrow municipal
scraper: the detailed-plan inventory in the official electronic seat. One live
planning instrument, with its full-document link, is extractable. This is partial
municipal coverage, not a granted-licence register or publication-ready map data.

## Identity and source discovery

- Generalitat local-entities register identifies Castelló, INE 46257, province
  València/Valencia, address Plaça de l'Ajuntament 8, postal code 46270:
  https://www.entidadeslocales.gva.es/index.php?Itemid=9&id=46257&lang=es&option=com_reglocal_entloc&task=muestraEntidad&tipo=1
  This is the Ribera Alta municipality formerly called Villanueva de Castellón,
  not Castelló de la Plana or Castelló d'Empúries. Those other municipalities'
  search results were excluded.
- https://www.castellosom.es/portada and the root variants disconnected during
  direct HTTP research. The indexed municipal PDF CDN
  https://cdn.digitalvalue.es/villanuevadecastellon/assets/6405c4fc7b27353f17ee7427
  also disconnected. Search snippets are discovery leads, not extracted records.
- https://www.elmiragall.org/ is the municipal bulletin (HTTP 200). Its announcement
  of the new castellosom.es domain corroborates the principal website:
  https://www.elmiragall.org/nou-domini-i-nou-espai-castellosomes-per-a-l039ajuntament-de-castello/
  No generic bulletin stories were converted into projects.
- https://www.castellopoble2030.com/documentacio/ (HTTP 200) lists the local urban
  agenda diagnosis, action plan and participation report, alongside national
  material. https://www.castellopoble2030.com/castello-poble-2030/proj-castello/
  exposes participation information, not an inventory of physical projects.
  These are research leads outside the implemented detailed-plan scope.

## Official inventory used

All following URLs returned HTTP 200 anonymously, without credentials:

1. https://castello.sedelectronica.es/transparency — public transparency root.
2. https://castello.sedelectronica.es/transparency/73652f4c-3bbc-47f6-a698-4cd4c78220e5/
   — section 6, urban planning and environment.
3. https://castello.sedelectronica.es/transparency/47001e76-9560-4fb3-991e-da5e553aefed/
   — section 6.1. Its child counts are PGOU: 0, normativa: 1, agreements: 0.
4. https://castello.sedelectronica.es/transparency/fbe02fb5-91ad-4e35-b687-4213d8452fda/
   — PGOU folder explicitly says no items found. It does not establish that the
   municipality has no general plan.
5. https://castello.sedelectronica.es/transparency/1fd32726-d72d-4838-8d29-9a0217fbe2ce/
   — normative inventory, one document: `PLA D'ORDENACIÓ DETALLADA COMPLET`.
   Its link description is `Aprovació definitiva del Pla d'Ordenació Detallada`.
6. https://castello.sedelectronica.es/preview-document/42dfa6a1-f51a-4f2a-b15d-3556257747a3
   — persistent document preview, matching plan title and embedded PDF. Reports
   creation metadata `06-may-2025 9:04:30`. This is retained as archive metadata
   text, **not** used as agreement, approval or publication date. Those dates
   remain null. The definitive-approval phase is attributed to the inventory's
   own link description, not inferred from a date or PDF contents.

The anonymous Wicket folder controls redirect to the persistent folder URLs;
no interactive session tokens are hardcoded. The adapter uses those public URLs.
The PDF endpoint returned `application/pdf`, but its stream exceeded the 25 MB
research cap. The binary was not archived or parsed; no claims about its internal
text, approval dates, coordinates or planning validity are made. The stable
preview link is retained rather than an ephemeral PDF/session URL.

## Extraction contract and limits

Each backfill/update refreshes the same current folder. It fetches the parent
count, then all document links in the inventory table and the matching previews.
Unique document count must equal the advertised parent count. An active next/more
control, unexpected title/host, missing heading, changed PDF preview or empty
inventory fails explicitly. There is no page limit or silent pagination cutoff.
The current one-document inventory has no continuation control. This is complete
for this folder only, not all planning in Castelló.

Documents for the named detailed plan are grouped into one instrument, deduplicated
by persistent document URL, retaining document titles, descriptions and links.
The stable record identity uses the inventory and instrument name; adding an
annex does not create another instrument. An unreviewed instrument added to the
folder fails for review. Forms, tender announcements and navigation are excluded.
No granted licences are asserted. Each HTML request has a 30-second timeout and
2 MB cap. Optional capture_dir writes original HTML evidence.

No geometry has been extracted from the document; coordinates and geometry stay
null, publication_ready is false. No centroid or jitter is substituted. Scheduling,
jitter and licences are disabled in the manifest. The shared entity policy
classifies this planning record as pendiente/insufficient_identity_evidence, with
activity_eligible=false; extraction success does not bypass that downstream gate.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_castello`: six tests pass. Covers real instrument
  semantics, date nulls, document grouping/deduplication and stable ID, forms and
  login rejection, parent count/pagination failures, external-host rejection and
  manifest/registry adapter loading.
- Real live extraction through `load_portal_adapter(load_manifest('castello'))`
  and `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: one record,
  status ok. The registry's entity-policy annotation was included.
- `evidence/proyectos.jsonl`: actual live planning instrument.
- `evidence/validation.json`: live_records=1, source_urls, limitations and policy
  report. `live-parent.html`, `live-inventory.html`, and `live-document-*.html`
  are the actual adapter source captures; other HTML files record discovery.

Evidence stays local. Only the manifest, this research document, the adapter and
its parser tests are source additions. No dependencies or shared files changed;
no publish, deployment, database, PR or git mutation operations were performed.
