# Sant Esteve Sesrovires — INE 08208, Barcelona

Verified live on 2026-11-08 using the preinstalled Python virtual environment.
This adapter covers a finite snapshot of three official municipal document
inventories. It does not claim complete municipal coverage, current legal-status
verification, or a granted-licence register. Scheduling and missing-coordinate
jitter are disabled. Records have `publication_ready: false`.

## Discovery and official provenance

The municipal [Urbanisme index](https://www.sesrovires.cat/temes/urbanisme)
links the six planning/management categories below. All six category pages were
fetched successfully over HTTPS; captures are under local `evidence/`.

Extracted inventories:

- [Gestió urbanísitca vigent](https://www.sesrovires.cat/temes/urbanisme/planejament-vigent/gestio-urbanisitca-vigent/):
  three instruments: urbanization of Polígon Industrial Sesrovires (12 links),
  reparcelation of that industrial estate (31 links), and the modified
  urbanization works project for Can Margarit (10 links). The headings explicitly
  say definitive approval. The urbanization and reparcelation are distinct
  instruments even though they concern the same estate.
- [Planejament general en tràmit](https://www.sesrovires.cat/temes/urbanisme/planejament-en-tramit/planejament-general-en-tramit/):
  one initial-approval PGOM amendment for SUP 05–Industrial SEAT, with 11 links
  (memory, environmental report, mobility study and plans).
- [Gestió urbanística en tràmit](https://www.sesrovires.cat/temes/urbanisme/planejament-en-tramit/gestio-urbanistica-en-tramit/):
  initially approved preliminary urbanization project for the Sant Joan,
  Martorell and Sucre streets (one link); complementary urbanization project
  improving access from B-224 to Polígon Industrial Sesrovires (two links).
  The latter has no explicit approval phase in its heading, so `fase` is null.
  Its allegation form is retained as `formulario_auxiliar` within that instrument,
  never counted as a separate project or granted licence.

Other inspected sources, outside this deliberately limited extraction:

- [Planejament general vigent](https://www.sesrovires.cat/temes/urbanisme/planejament-vigent/planejament-general-vigent/):
  general links to planning and the territorial commission, no local instrument
  document sections of the extracted kind.
- [Planejament derivat vigent](https://www.sesrovires.cat/temes/urbanisme/planejament-vigent/planejament-derivat-vigent/)
  and [Planejament derivat en tràmit](https://www.sesrovires.cat/temes/urbanisme/planejament-en-tramit/planejament-derivat-en-tramit/):
  no instrument document sections in their HTML responses.
- [Obres La Coma](https://www.sesrovires.cat/temes/obres-la-coma): separate works
  resource with several phases, a 2010 project and recent news. Not included;
  it needs its own grouping of distinct projects and phases. This is an explicit
  coverage exclusion, not an assertion that the municipality has only six projects.
- The index describes the PGOM and links an older Generalitat RPUC entry point;
  the complete RPUC catalogue and the Can Serra subsection are not crawled.
- An initial probe of `/temes/obres` returned 404. The actual navigation target is
  `/temes/obres-la-coma`, inspected above.

## Extraction rules and limitations

One row per `.subtitle` instrument and its immediately following `.ddbbtext`
attachment block; each document retains its title, original absolute URL and
inventory provenance. All 67 published links are retained, including volumes,
plans, certificates, annexes and the auxiliary allegation form. URLs include the
municipality's official seu-e.cat document repository and legacy seu.cat file
endpoints. Links are evidence supplied by the municipal inventory; this scraper
does not download or authenticate their PDF contents or guarantee availability
of every legacy endpoint.

The three extracted pages are unpaginated. There is no record limit or first-page
cutoff. Pagination controls, unknown attachment destinations, missing sections,
unassociated document blocks, form-only sections and duplicate instruments fail
extraction rather than silently produce an incomplete snapshot. All three pages
must succeed before the output file is atomically replaced. Update refreshes the
whole snapshot; the state file is not a date cursor.

The source labels these pages as updated in March 2016. Those labels are neither
project publication dates nor agreement dates. `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, and `fecha_aprob` remain null. `fase` and `estado_fuente` report
what the inventory says, without implying independent verification of legal
status in 2026. No coordinates are supplied in the parsed inventories; `lat`,
`lon` and `geometry` remain null. No municipal centroid is substituted. No
procurement notices, licence applications or unrelated news are emitted.

## Validation and reproducibility

Run from the repository root with the required runtime:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sant_esteve_sesrovires -v
```

Six tests passed: document grouping and identity across reordering; separate date
and phase semantics; auxiliary-form handling; PGOM classification; rejection of
pagination, changed markup, procurement/licence headings and incomplete sections;
atomic failure on cross-inventory duplicates; manifest/adapter resolution.

A real `SantEsteveSesroviresAyuntamientoAdapter.backfill_proyectos` call fetched
all three source pages and wrote **6 actual records with 67 document links** to
`evidence/proyectos.jsonl`. `evidence/validation.json` records `live_records`,
source URLs, limitations, capture SHA-256 hashes, test command and per-instrument
counts. Configure `capture_dir` on the adapter to save the fetched HTML in the
same way. Evidence is local and excluded from source delivery. No shared source,
dependencies, git internals, database, deployment or publishing operations were
modified or used.
