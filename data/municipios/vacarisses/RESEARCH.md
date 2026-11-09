# Vacarisses — INE 08291, Barcelona, Catalunya

Verified live on 2026-11-08 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One adapter covers the current municipal Urbanisme inventory. Scheduling,
missing-coordinate jitter and licence extraction are disabled.

## Official source discovery and coverage

The live municipal [Urbanisme inventory](https://www.vacarisses.cat/ajuntament/normativa/urbanisme)
exposes six entries in a nonpaginated menu, repeated for responsive layouts.
The adapter discovers these links from the inventory's content menu, deduplicates
URLs and visits every linked detail. It does not use a fixed six-URL whitelist
or a record limit. Pagination controls cause an explicit failure rather than a
silently incomplete snapshot. Unexpected detail content or unclassified attached
documents also fails before replacing the existing output.

| Official inventory entry | Extracted instruments | Agreement date | Linked PDFs |
| --- | --- | --- | --- |
| [Ca l'Oliva](https://www.vacarisses.cat/ajuntament/normativa/urbanisme/ca-loliva) | Urbanisation; reparcellation | 2026-03-09 | 4 |
| [El Fresno](https://www.vacarisses.cat/ajuntament/normativa/urbanisme/el-fresno) | Urbanisation; reparcellation | 2026-03-09 | 4 |
| [El Pou Gran](https://www.vacarisses.cat/ajuntament/normativa/urbanisme/el-pou-gran) | Urbanisation | 2026-03-09 | 2 |
| [La Farinera](https://www.vacarisses.cat/ajuntament/normativa/urbanisme/la-farinera) | Urbanisation; reparcellation | 2026-03-09 | 4 |
| [Estudi de detall al C/ Manresa](https://www.vacarisses.cat/ajuntament/normativa/urbanisme/estudi-de-detall-al-c-manresa) | Modification of detail study, Manresa 40–42 | 2026-05-11 | 2 |
| [El Ventayol](https://www.vacarisses.cat/ajuntament/normativa/urbanisme/el-ventayol) | Reparcellation | 2026-09-28 | 2 |

These are nine genuine instruments, not eighteen projects. Each notice and its
technical document remain together in `documentos`, including the source page
URL, label and exact download URL. Ventayol's memory and graphical volume are
likewise grouped into one instrument. Stable IDs hash the detail URL plus the
instrument type, independently of document order or page modification date.

The municipal inventory also links the [RPUC](https://planejamenturbanisme.territori.gencat.cat/rpucportal/#/inici)
for all planning dossiers. That wider register is not crawled. The municipal
[transparency planning page](https://www.seu-e.cat/web/vacarisses/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic)
also refers to RPUC/MUC rather than constituting the inventory implemented here.
Discovery also identified the official
[projects of regulations in progress page](https://seu-e.cat/ca/web/vacarisses/govern-obert-i-transparencia/accio-de-govern-i-normativa/normativa-plans-i-programes/memories-i-documents-dels-projectes-normatius-en-curs),
whose search-visible inventory mixes ordinances, a psychology service consultation
and an asphalt works project. It is outside this adapter's deliberately bounded
Urbanisme coverage. No claim is made to cover all municipal physical works,
planning history, public notices, or records from other inventories. Procurement
announcements, general urbanism rules, explanatory infographics, news and licence
application forms are not converted into projects or granted licences.

## Dates, provenance and uncertainty

The March approval dates come from the governing-body session narrative;
reparcellation is explicitly said to have been approved in the same session.
The initial approval phase comes from the attached announcement labels or the
explicit `va aprovar inicialment` narrative. `fecha_acuerdo` and `fecha_aprob`
refer to that agreement; `fecha` is null. The `Darrera actualització` dates are
stored only as `fecha_actualizacion_fuente`: March 27 for Ca l'Oliva/El Fresno,
March 16 for Pou Gran/La Farinera, June 9 for Manresa and October 8 for Ventayol.
They are not publication or approval dates. No explicit project publication date
is extracted, so `fecha_publicacion` remains null. No dates are derived from the
crawl date, statutes quoted in the text, PDF file names or unparsed PDF metadata.

Ventayol's municipal narrative calls the action urbanisation works but quotes
`PROJECTE DE REPARCEL·LACIÓ DE POLÍGON D’ACTUACIÓ URBANÍSTICA EL VENTAYOL DE VACARISSES`.
The adapter retains that quoted title as one reparcellation instrument, preserves
the full municipal narrative and adds `source_warning`; it does not manufacture
a second urbanisation project. Manresa concerns a detail-study modification for
nine grouped dwellings, not nine licences or proof of construction authorisation.

HTML pages supply the records. PDF links are retained as provenance; the adapter
does not parse their contents. Separate live validation verified HTTP success and
PDF signatures for all 18 document URLs using streamed requests consuming only
the initial 1024 bytes. Large technical files were not fully downloaded. PDF
plans may contain useful geometry, but no verified project geometry is extracted:
`lat`, `lon`, and `geometry` are null and `publication_ready` is false. No municipal
centroid or random point is substituted.

## Implementation and validation

The adapter implements all four portal methods. Project updates refresh the entire
inventory, writing atomically only after every detail parses successfully. Licence
methods return disabled with zero rows. HTTP calls use explicit timeouts, a user
agent, bounded HTML responses and municipal-host checks. Missing body, approval
narrative, source documents, unexpected links or changed inventory markup fail
explicitly instead of yielding placeholder records.

- `python -m unittest municipio.test_vacarisses -v`: 10 tests passed. Tests cover
  distinct instruments and grouped documents; agreement versus update/publication
  dates; statute-date exclusion; missing-date semantics; the Manresa study and
  Ventayol ambiguity; responsive-menu deduplication; pagination rejection;
  form/login/unclassified-document rejection; snapshot preservation on failure;
  update behavior, manifest loading and disabled licences.
- A real live extraction used `load_manifest('vacarisses')` and
  `load_portal_adapter`, then `backfill_proyectos`: 9 records, 6 detail pages,
  18 document links. Shared entity policy annotated the output successfully,
  with all 9 category classifications unknown; no classification is invented.
- `evidence/proyectos.jsonl` contains actual records. `evidence/validation.json`
  records the live count, source URLs, checks and limitations. Seven HTML captures
  and `evidence/document_checks.json` preserve the supporting live evidence.
  Evidence is local and is not part of the four source additions.
