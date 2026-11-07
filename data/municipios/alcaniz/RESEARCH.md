# Alcañiz — Teruel — INE 44013

Verified live on 2026-11-07 using the preinstalled batch virtualenv. This adapter
extracts genuine planning instruments and named physical public-work projects
from two current municipal inventories. It is a partial snapshot, not a complete
history of municipal activity. Licences and scheduling are disabled, missing
locations are never jittered, and every record has `publication_ready: false`.

## Official inventories

- [Municipal transparency Urbanismo](https://sede2.alcaniz.es/portal-transparencia/urbanismo)
  returned HTTP 200. Its content links to the municipal PGOU inventory and names
  two actual basic/execution projects: the Avenida de Aragón urban park
  remodelling and the covered semi-Olympic pool at Ciudad Deportiva de Santa
  María. Each has its own municipally published Dropbox link. These are project
  descriptions with documents, not procurement notices or granted licences.
- [Municipal Plan General de Ordenación Urbana inventory](https://www.alcaniz.es/index.php?option=com_content&view=article&id=894&Itemid=833&lang=es)
  returned HTTP 200 and lists written and graphic PGOU documentation, its BOP
  publication, and four numbered amendments under “Modificaciones aprobadas”.
  The PGOU is one instrument with 25 direct links, including map subindexes.
  Amendments 1–3 each have two links; amendment 4 has three, including the
  Art. 135 annex. None of these documents becomes a separate project.

The official inventory labels the PGOU BOP publication as 18 June 2013 and the
four amendment publications as 25 June 2015, 9 April 2019, 11 May 2021 and
27 December 2021. Only `fecha_publicacion` uses these dates. No agreement or
approval date is inferred from them, from the crawl date, filenames or the
general “aprobadas” heading. In particular, the inventory heading does not prove
that every aspect of amendment 2 was definitively approved. Approval scope and
dates require review of the underlying resolutions. `fase`, `fecha_acuerdo`,
`fecha_aprob` and generic `fecha` remain null.

Document provenance is retained as `procedencia_url` on every document.
Municipal planning documents are hosted on `h.alcaniz.es`, and some BOP links
point to the official Aragón bulletin service. The two Dropbox landing pages
(one PDF share and one folder share) returned HTTP 200 during research; this
does not establish approval, completeness or authenticity of their contents.
The adapter retains the exact published share URLs, including public share
parameters, and does not enumerate that folder or download the large binaries.

## Extraction boundaries

The adapter fetches both HTML inventories in full with a 35-second request
timeout and a 3 MB response bound. There is no record limit or date cutoff.
Neither reviewed inventory exposes pagination. Explicit next links or pager
markup raise an error; future pagination needs a traversal implementation.
Missing headings, missing publications, ambiguous amendment numbers, absent
project documents and unexpected public-work formats fail closed. Both pages
must parse before the output snapshot is atomically replaced. Updates refresh
the complete two-page snapshot rather than pretend to provide historical deltas.

PGOU map subindexes remain attached links and are not recursively crawled.
No PDF text, parcel data, geometry or project coordinates are extracted. There
is no verified granted-licence register in this implementation; licence methods
produce a disabled empty result. Forms, unrelated news, procurement listings
and application procedures are excluded from the extraction.

Record IDs are local stable keys for the PGOU, each numbered amendment, and
hashes of the published work titles. They are not invented municipal expediente
numbers. The registry's shared entity policy classified all seven live records
as `pendiente` (`insufficient_identity_evidence`); its report is preserved in
local evidence. These genuine source inventory records still need independent
identity review for downstream activity eligibility, as well as verified
geometry before map publication. No shared policy was changed to bypass that.

## Validation and local evidence

- `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_alcaniz -v`
  — 7 tests passed. Tests cover document grouping, date semantics, no invented
  coordinates, exclusion of licence forms and procurement text, duplicate work
  paragraphs, pagination detection, changed inventories and output preservation
  on a failed refresh.
- Live extraction via `load_manifest('alcaniz')`, `load_portal_adapter` and
  `backfill_proyectos`: 7 records, 36 retained document links, 7 unique IDs.
  The shared entity-policy wrapper was exercised, too.
- `evidence/proyectos.jsonl`: actual live records with shared policy annotation.
- `evidence/validation.json`: live record count, source URLs, all document URLs,
  extraction result, test command and limitations.
- `evidence/urbanismo.html` and `evidence/planeamiento.html`: full live source
  captures from the adapter. `evidence/proyectos.entities.json`: shared policy
  report. All evidence is local and excluded from the four source deliverables.

No credentials, other workspaces, database connections, publishing commands,
dependency changes or shared source changes were used.
