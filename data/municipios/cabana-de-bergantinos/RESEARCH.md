# Cabana de Bergantiños — INE 15014, A Coruña

Verified on 2026-11-09 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One real physical expropriation project extracted. Coverage is deliberately
partial: the municipal public-information inventory described below, not all
municipal planning, works or licences. Scheduling and coordinate jitter are
disabled. No verified granted-licence inventory was found in the inspected pages.

## Official source discovery

- [Municipal electronic office](https://sede.cabana.gal/sxc/gl/) links its
  transparency portal and urban-planning procedures. Application forms and prior
  communications are not granted licences and are excluded.
- [Transparency portal](https://sede.cabana.gal/sxc/gl/portal_transparencia/)
  links both Plans e Programas and Proxectos Normativos.
- [Plans e Programas](https://sede.cabana.gal/sxc/gl/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html)
  has a PXOM link to the historical SIOTUGA municipal inventory, with
  `idconcello=15014`. It also mentions a forest-fire prevention plan, without a
  technical-document link in the inspected HTML. Neither becomes an extracted
  record from navigation or a name alone.
- [SIOTUGA municipal query](https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=15014)
  returns HTTP 200 but a municipality search form without dossier rows. The
  adapter does not claim to extract this planning inventory.
- [Municipal Plan Urbanistico page](https://cabana.gal/documentos/plan-urbanistico/)
  describes initial approval of a PGOM, links a DOG notice and a planning PDF,
  and displays 24 March 2018 as the page date. It is not evidence that a new plan
  is definitively approved or currently in force. This historical page is outside
  the implemented inventory; its page date is not used as an approval date.
- **Implemented inventory:** [Proxectos Normativos](https://sede.cabana.gal/sxc/gl/portal_transparencia/Relevancia_Juridica/Proyectos_Normativos/Proyectos_Normativos.html),
  HTTP 200. Despite the broad section name, its **Información pública** list
  exposes a named, physical project: “Proxecto de expropiación dos bens e dereitos
  necesarios para a execución da Estrada en CANDUAS.” There is one project and no
  pagination in the live HTML. Generic regulatory consultations are excluded.
- [Technical PDF](https://sede.cabana.gal/sxc/export/sites/cabana/recursos/downloads/portal_transparencia/140425EXPROPIACION-CON-CESIONES-CANDUAS.pdf),
  HTTP 200, 7,528,490 bytes; SHA-256
  `1dca5e53d9d91866536c501843ba6c327a20ccc4e8ddb564307edee267968f65`.
  Local `pdftotext -layout` inspection confirms the document's title and object:
  expropriation to open the road in Cánduas in execution of municipal planning.
  It identifies the Concello as expropriating entity and beneficiary. This is
  technical project content, not a procurement-only announcement.

## Semantics and coverage

The inventory explicitly labels the project as **información pública**. The PDF
cover says “APROBACIÓN INICIAL”, bears a drafting month of January 2024 and a
digital signature dated 31 March 2025. These are different kinds of evidence:
none establishes the actual agreement or publication day. All record date fields
remain null. Dates of the antecedent 1999 PXOM inside the PDF are not dates of
this road project. The filename prefix is also not used as a date.

The adjacent `[BOP]` text is not a hyperlink. The generic BOP homepage in the
site footer is not an announcement and is not attached to the record. No BOP
announcement or agreement date is claimed.

The adapter reads the entire single HTML inventory and groups technical PDFs
within each project list item as one record, retaining their titles and URLs.
Identity uses the primary technical-document URL, independent of crawl time or
minor title changes. It validates every attached PDF and records its hash and
size. A full refresh serves both backfill and update; no timestamp cutoff skips
records. Conventional pagination markers trigger an error, rather than silently
returning a first page. Missing content, empty inventories, unexpected document
origins, redirects and invalid/oversized responses also fail before writing a
new output snapshot. HTML is limited to 2 MB and each PDF to 32 MB.

No geometry is extracted from the PDF's plans. `lat`, `lon` and `geometry` are
null; `publication_ready` is false. No municipal centroid, inferred parcel
position or artificial jitter is substituted. The snapshot does not establish
whether the road is built or whether the project has progressed after the phase
shown on the inventory. Projects outside this expropriation list are not covered.

## Validation and local evidence

- `python -m unittest municipio.test_cabana_de_bergantinos -v`: six passing tests
  covering grouped documents, unknown dates/geometry, exclusion of forms and
  navigation, pagination detection, document origin, stable identity and output
  handling on document failure.
- Direct live `CabanaDeBergantinosAyuntamientoAdapter.backfill_proyectos`:
  `status=ok`, **1 record**, technical PDF fetched and verified.
- `evidence/proyectos.jsonl`: actual live record and document provenance.
- `evidence/validation.json`: live count, source URLs, verification time,
  runtime, test result and coverage limitations.
- `evidence/proyectos-normativos.html` and the PDF named by its SHA-256 are
  captures from the adapter's live run. `transparencia.html`, `inventory-0.html`,
  `inventory-1.html` and `siotuga.html` retain discovery responses;
  `canduas.txt` contains the locally extracted PDF text for source review.

Evidence is local and excluded from the four source deliverables. No shared
modules, dependencies, credentials, database or deployment operations are used.
