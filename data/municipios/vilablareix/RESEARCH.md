# Vilablareix — Girona — INE 17215

Verified live 2026-11-09 using the preinstalled municipal virtualenv. This adapter
covers a deliberately bounded municipal **technical planning document collection**,
not all current planning, public works, or granted licences. Four genuine planning
instruments retain 30 unique official document links. Presence in this collection
does not establish current legal force. Scheduling and coordinate jitter are off;
licences are disabled; all records have `publication_ready: false`.

## Official source discovery

- https://www.vilablareix.cat/ajuntament/arees-municilpals/urbanisme-i-territori
  (200): municipal urbanism landing page. Links the planning map, RPUC query with
  `municipiSel=17215`, electronic planning board, and licence application service.
  The municipal map explicitly does not replace the legal planning text.
- https://www.vilablareix.cat/taxonomy/term/22 (200): municipal collection headed
  Planejament en tramitació in discovery; live HTML has 31 document rows, 30 unique
  PDF URLs (the older Marroc II memory is repeated). No pagination is exposed.
  This is the extraction source, captured by the adapter as `inventory.html`.
- https://seu.vilablareix.cat/seuelectronica/zonapublica/seu/TaulellAnuncis/TaulellAnuncis.aspx?idAccio=2&idMenu=22
  (200): separate official notice inventory, **page 1 of 4**, with ASP.NET
  postback pagination and document actions. Current notices include Mas Marroch
  and Girona FC planning. Discovery capture only: **none of its pages contributes
  extracted records**. Its 2026 notice publication dates are not dates for the
  historical instruments in the technical collection. Full board coverage needs
  a separate traversal and identity/grouping implementation.
- Municipal RPUC link:
  http://ptop.gencat.cat/rpucportal/AppJava/cercaExpedient.do?sortColumn=data&fromPage=load&reqCode=cerca&sortDirection=1&comarcaSel=20&pagingPage=1&municipiSel=17215&
  Discovery only, not extracted; no claim of complete RPUC coverage.
- The municipal licence link is a service for applications/requirements, not a
  granted-licence register. No licence records are emitted.

## Instrument identity and document grouping

The PDF memories were downloaded and inspected with `pdftotext -layout`; local
PDF and text captures are in `evidence/`. Grouping uses a reviewed filename map,
not proximity of rows or arbitrary document counts:

1. **NNSS — Sectors industrials (16)**: one document. The cover of
   `2013_Mod_NNSS_c16.pdf` identifies the instrument and November 2013 authorship.
2. **Modificació puntual del Pla parcial — El Perelló i Can Pere Màrtir**:
   eight documents. `Memoria_PP_2.pdf` identifies the modification, February 2009,
   and “document per a l'aprovació inicial”; its index names plans 01, 06–07, 09
   and 10. `090528_MPElPerello_NUcat.pdf` article 1 identifies the same plan
   modification. The collection contains variant norms and plans; retained
   together without asserting that one is the currently effective version.
3. **Pla especial de regulació d'usos del sòl no urbanitzable**: nine documents.
   `PERUSNU_Vilablareix.pdf` identifies the plan (July 2008) and its contents;
   PERUSNU-prefixed inventory rows group the announcement and thematic maps.
   `APROVACIO_INICIAL_BOP.pdf` is a whole BOP page containing other municipalities
   too. Only its Vilablareix notice concerns this instrument. Manual inspection
   identifies publication 2008-12-22 and agreement 2008-11-10; the adapter does
   not parse PDF text, so neither date is populated automatically.
4. **NNSS — U.A. Marroc II**: twelve documents. `UA3_Memoria.pdf` (March 2009)
   and `MEMORIA_MODIFICACIO_PUNTUAL_DE_LES_NORMES_SUBSIDIARIES.pdf`
   (November 2008) both explicitly name U.A. Marroc II. They are versions of the
   same instrument, not two projects. Associated plans and convention are retained.

The instrument titles are normalized from the inspected covers and inventory
text; the individual document titles and URLs are parsed from live HTML.
Stable local IDs name the reviewed instruments, not invented expediente numbers.
Each document retains the originating inventory URL. No separate record is made
for a map sheet, duplicate download/view link, convention attachment, or notice.

## Semantics and extraction safeguards

The inventory has no explicit dates. All generic, publication, agreement, and
approval date fields remain null. Cover dates, dates in filenames, historical
approvals in background paragraphs, and HTTP timestamps are not approval dates
for these instruments. No definitive/initial phase is inferred from collection
membership. No point or geometry has been verified: `lat`, `lon`, and `geometry`
are null; PDF maps are retained as documents only.

Backfill and update refresh the complete reviewed collection. HTTP failures,
unexpected redirects, response sizes above 2 MB, missing documents, unknown
attachments, changed row markup and detected pagination fail the extraction
before replacing output. This intentionally requires review if inventory contents
change, rather than silently losing records or associating unknown documents.
The source is a historical collection even though it is currently accessible;
this implementation makes no completeness claim for present-day activity.

## Validation and local evidence

- `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_vilablareix -v`:
  five parser/manifest tests cover grouping, deduplication, null semantics,
  missing/unknown inventory content, pagination rejection and disabled licences.
- Real `VilablareixAyuntamientoAdapter.backfill_proyectos` HTTP extraction:
  four records and 30 unique documents in `evidence/proyectos.jsonl`.
- All 30 linked documents fetched separately, checked for successful HTTP and PDF
  signature, and captured locally. `evidence/validation.json` includes counts,
  URLs, byte counts, SHA-256 hashes and coverage limitations.
- Evidence is local and excluded from the four source files. No dependencies,
  shared sources, credentials, database, publishing or deployment were used.
