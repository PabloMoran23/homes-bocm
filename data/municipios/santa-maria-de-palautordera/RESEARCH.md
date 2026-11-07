# Santa Maria de Palautordera — INE 08259, Barcelona

Verified 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One municipal adapter covers two official, publicly accessible inventories.
The live snapshot contains **20 records: 19 planning instruments and one physical
public-works project**. Coverage is partial and `publication_ready` is false.

## Official source inventory

1. [Municipal POUM inventory](https://www.smpalautordera.cat/ajuntament/normativa/poum-pla-dordenacio-urbanistica-municipal)
   — live HTTP 200 HTML, captured as `evidence/poum.html`. Municipal identity is
   displayed in the page heading/narrative and footer (NIF P0825900D). Contains:
   the consolidated POUM, 11 POUM modifications, two partial-plan modifications,
   and five special plans/modifications. The POUM's seven attachments (maps,
   searchable/scanned plan, regulations and DOGC notice) are grouped into one
   instrument. Each of the 18 listed instruments is a separate record, retaining
   its municipal PDF or official RPUC dossier URL. All links in each list item
   are retained together. The linked map folder is retained under `enlaces`;
   its Google Drive contents are outside this scraper's inventory.
2. [Municipal ordinary works inventory](https://www.smpalautordera.cat/el-municipi/obra-municipal-ordinaria)
   — live HTTP 200 HTML, captured as `evidence/obra-municipal.html`. One document
   explicitly named “Aprovació incial del projecte d'estabilització del marge
   esquerre Torrent del Reguissol al C/ Nou núm. 30-46”. This is a physical works
   project, with initial approval stated by its attachment title, not a tender.
   The PDF is advertised as 313.9 MB; its link and municipal provenance are
   retained, but the PDF was not downloaded or parsed. No approval date is
   inferred from the filename, crawl time or page update timestamp.
3. [Provincial official planning inventory (CIDO)](https://cido.diba.cat/normativa_local/6638554/planejament-urbanistic-ajuntament-de-santa-maria-de-palautordera)
   — discovered during official-source research. Shows later planning notices,
   including 2026 entries, demonstrating that the municipal POUM inventory
   (last updated 2023-11-29) is not a complete current history. CIDO and individual
   bulletin notices are outside this adapter's extraction scope. For example,
   [BOPB PMU-1 notice](https://bop.diba.cat/anunci/3897777/aprovacio-inicial-de-la-proposta-de-modificacio-puntual-del-pla-de-millora-urbana-pmu-1-ajuntament-de-santa-maria-de-palautordera)
   has publication date 2026-02-18; it is not included or assigned an inferred
   agreement date.
4. [Major works licence procedure](https://www.smpalautordera.cat/serveis-i-tramits/tramits-i-gestions/llicencia-dobra-major.html?lang=ca)
   — application instructions and blank forms, not granted licences. Excluded.
   No verified public granted-licence inventory is claimed; licensing is disabled.

## Extraction semantics and coverage

The adapter refreshes both inventories as one complete snapshot for backfill and
update. There is no date cutoff or record cap. The currently served inventories
are single-page document/list pages. Pagination controls or next-page links cause
an explicit error, so a future paginated inventory cannot silently lose pages.
Missing headings, missing documents, empty inventories, unsupported list items,
non-HTML responses and oversized responses also fail visibly. Output is replaced
atomically only after both pages parse, preserving the previous snapshot on error.

The base POUM narrative explicitly gives definitive approval **2011-09-22** and
DOGC publication **2011-12-15**, stored separately as `fecha_aprob` and
`fecha_publicacion`. `fecha_acuerdo` and generic `fecha` are null. Derived-plan
labels have reference years, preserved as `anio_referencia_fuente`; these are
not promoted to exact dates or used to assert an approval phase. The works
record has initial-approval phase from the municipal title and null dates.

Stable record identities use the inventory URL for the base POUM, and the first
linked municipal PDF/RPUC dossier for individual instruments. RPUC numeric IDs
are preserved as `rpuc_id`, not represented as municipal expediente numbers.
Document records retain `titulo`, `url`, and `url_fuente`. RPUC dossier contents,
PDF contents, any supersession relationships, and the linked map folder have
not been crawled; the adapter reports what the municipal inventory lists rather
than asserting every instrument's present legal validity.

No verified instrument geometry or coordinates were extracted. All `lat`, `lon`
and `geometry` values are null; no municipal centroid or jitter substitutes for
project locations. The manifest sets `geocode.jitter_missing: false`,
`schedule.enabled: false`, and `licencias.enabled: false`.

## Validation and local evidence

- `python -m unittest municipio.test_santa_maria_de_palautordera -v`: **8 tests
  passed** using the runtime above. Covers date separation, missing publication
  dates, grouped/deduplicated documents, stable IDs, reference-year semantics,
  rejection of forms/login/changed markup, pagination failure, physical works
  recognition, atomic snapshot behavior and manifest loading.
- Real `SantaMariaDePalautorderaAyuntamientoAdapter.backfill_proyectos` fetched
  both pages and produced **20 unique records**, all INE 08259, with no fabricated
  dates or coordinates. This was a live extraction, not fixture replay.
- Local `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/poum.html`
  and `evidence/obra-municipal.html` preserve the output, counts, source URLs,
  limitations and source captures. Evidence is not source to be committed.
- No shared source files, dependencies, credentials, remote repository services,
  databases or deployment tools were used or modified.
