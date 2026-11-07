# Sant Sadurní d'Anoia — INE 08240, Barcelona

Verified live on 2026-11-07 using the preinstalled batch virtual environment.
This adapter covers actual planning instruments published in the municipal-linked
POUM viewer. It is a partial consultation inventory, not a complete municipal
project history or a granted-licence register. Scheduling and licence extraction
are disabled; missing coordinates are never replaced or jittered.

## Official discovery and provenance

- https://santsadurni.cat/urbanisme — municipal Urbanisme i Obres page, HTTP 200.
  Its “Planejament urbanístic” link points to `http://mapa.psig.es/ssa/`.
  The adapter uses the working HTTPS equivalent and verifies that municipal
  delegation on every run. The municipal response declares ISO-8859-1.
- https://mapa.psig.es/ssa/ — HTTP 200. The municipal-linked POUM viewer explicitly
  warns that its copies have **no normative value**. Definitively approved
  instruments may also be affected by subsequent court decisions. The original
  normative documents belong to the Generalitat's RPUC. The scraper records the
  inventory's classification, not an independent legal-validity determination.
- https://mapa.psig.es/ssa/normativas/ — HTTP 200, the iframe linked by the viewer.
  Its public jsTree interface calls `?operation=get_node&id=%23` for the root,
  `get_node` for every lazy folder and `get_content` for each selected PDF.
  `get_content` returns a JSON pointer, not the PDF itself. The adapter validates
  that pointer against the observed server prefix and emits the corresponding
  encoded HTTPS PDF URL, retaining the original node ID and source inventory.
- https://seu-e.cat/ca/web/santsadurnidanoia/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200. Current transparency page links the RPUC municipal search with
  `municipiSel=08240` and MUC; it does not contain instrument rows. Its displayed
  update date (16/09/2026) is **not** an agreement or project publication date.
- https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08240
  — discovered official municipal-search entry, retained here as provenance;
  RPUC's application shell is not used as a source of invented project rows.

## Coverage and grouping

The complete tree traversal produced **16 instruments and 100 PDF links**:

- One POUM record with 85 documents: memories, norms, annexes, environmental
  memory, all seven plan series, DOGC publication and the POUM agreements bundle.
- Eight POUM modifications: Caves Vilarnau, UCSA, Can Ferrer I, Agromillora SNU,
  Freixenet, Covides, ground-floor residential use, and vitivinicultural use in
  zoning keys 9 and 10. File labels range from 2016 to 2023.
- Seven special plans: Biblioteca, Cal Mota, HD La Triola, Av Francesc Macià 25–27,
  Casa Mestres, Escola Sant Josep and Ateneu. File labels range from 2012 to 2025.

Base-plan documents are grouped into one instrument. In the later general and
derived planning categories, the source's numbered entry and year define a
group: additional PDF pieces for that entry remain attached to the same record.
No document is emitted as a separate project merely because it is a PDF.
All selected document titles, URLs and original node IDs are retained.

Fifteen leaves were explicitly excluded and listed in validation evidence:
viewer thumbnail images, generic RPUC/contact text pointers, an administrative
appeal decision, a court judgment, four independent agreements, TUC documents
and acoustic-map documents. They are not claimed as separate planning projects.
The POUM legal effects of the appeal and judgment are **not** resolved here.
Procurement, forms, council agendas and general news do not generate records.

Every inline child and lazy folder is traversed, including excluded categories.
The current tree uses no numbered pagination or page-size parameter. Unexpected
child representations, repeated IDs, safety bounds, unknown entries in selected
planning categories, missing provenance and failed HTTP requests raise errors;
they never cause a successful truncated snapshot. Update repeats the full
inventory refresh. Output is replaced atomically only after successful parsing.

## Dates, geometry and downstream limits

`fecha`, `fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` stay null because
the adapter parses the inventory, not PDF text. A filename year is retained only
as `anio_etiqueta_documental`; it is never converted to January 1 or an approval
date. The shared directory's 30 September 2010 date is not applied to its later
instruments. Phase states explicitly that definitive approval is the inventory's
classification.

Manual source sampling verified three genuine PDF responses: base DOGC edict,
Caves Vilarnau modification and Ateneu special plan. The DOGC sample distinguishes
the agreement of 30 September 2010, the edict of 4 April 2011 and publication in
DOGC 5863 on 20 April 2011. These dates are **not automatically extracted** or
hardcoded by the scraper. The document sample also shows that approval has
conditions/exceptions; the viewer cannot establish unrestricted current validity.

No instrument geometry has been verified. `lat`, `lon`, `geometry` remain null
and `publication_ready=false`. Neither municipal centroids nor map search UI
coordinates are instrument locations.

The shared `entity_policy` guard currently marks these 16 inventory identities
as `pendiente` / `insufficient_identity_evidence`, producing
`adapter_incident: unknown_entity_spike` when loaded through the registry.
The inventory has real named instruments but does not expose expediente numbers;
the adapter does not fabricate them to satisfy that guard. Extraction readiness
does not imply downstream activity eligibility or publication readiness. No
shared policy or source files were changed.

## Reproduction and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Parser tests:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sant_sadurni_d_anoia -v
```

Seven tests cover complete nested traversal, cycles, unknown pagination, wrong
municipality, empty inventory, document grouping/exclusions, unknown planning
entries, safe PDF pointer resolution, and municipal provenance.

Live extraction (from repository root):

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

manifest = load_manifest('sant-sadurni-d-anoia')
manifest.portal.config['evidence_dir'] = str(Path('evidence').resolve())
result = load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

`evidence/proyectos.jsonl` contains the actual live records;
`evidence/validation.json` contains live count, document count, all 127 requested
source URLs, exclusions and limitations. Each live HTML/API response is captured
under its URL SHA-256 filename (`.capture`). Research snapshots and three sampled
PDFs are also local evidence. Document URLs are retained for all 100 PDFs; the
adapter does not download every PDF binary. Evidence is local and uncommitted.
