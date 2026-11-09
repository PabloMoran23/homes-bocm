# Viladecavalls — INE 08300, Barcelona

Verified 2026-11-08 using the preinstalled Python 3.12 virtual environment.
The adapter implements a deliberately partial snapshot of the official municipal
current-planning inventory, with four genuine instruments/projects and seventeen
retained document links. It does not claim a complete historical planning register,
a public-works register or a granted-licence register. Scheduling and missing-point
jitter are disabled. No coordinates or geometries are invented; all records have
`publication_ready: false`.

## Official sources discovered

- Municipal inventory (HTTP 200, live extraction source):
  https://www.viladecavalls.cat/seu-electronica/normativa-municipal/normativa-urbanistica/planejament-vigent
- Municipal normative index identifies that inventory as current planning:
  https://www.viladecavalls.cat/seu-electronica/normativa-municipal/normativa-urbanistica
- Municipal Urbanisme service describes the PGO and its revision as the principal
  municipal planning instrument. Its licence links are procedures, not grants:
  https://www.viladecavalls.cat/seu-electronica/oferta-de-serveis/area-de-territori/urbanisme/servei-durbanisme
- The inventory's RPUC link:
  https://www.viladecavalls.cat/seu-electronica/normativa-municipal/normativa-urbanistica/planejament-vigent/planejament-urbanistic
  redirects to
  `http://ptop.gencat.net/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08300`.
  The legacy destination failed DNS resolution. Its municipality selector also
  explicitly identifies INE 08300. No RPUC dossiers or completeness are claimed.
- The transparency planning page also refers to Generalitat RPUC/MUC:
  https://seu-e.cat/ca/web/viladecavalls/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  This is not an additional project inventory extracted by this adapter.

## Extraction decisions

The finite municipal content page contains no pagination. The adapter reads all
selected instruments and attachments without a record cap or date cutoff; it
rejects pagination markers rather than silently accepting only a first page.
Unexpected login/content structure, missing required sections, missing PGO norms,
empty specific-project output and external PDF hosts fail explicitly. Updates
refresh the full selected snapshot, replacing the output atomically after parsing.

The PGO is one record with ten sector plan PDFs and three written-document PDFs.
An unlinked economic/financial-study label is not invented as a document URL.
Each specific instrument is one list item: Sabadell urbanization (one PDF), Can
Mitjans sector 13 compensation statutes and bases (two PDFs together), and the
asphalt-plant preliminary project (one PDF). The latter is an actual technical
anteproyecto, not proof of a granted licence, construction start or completion.
The compensation phase explicitly refers to statutes/bases approval, not approval
of the entire partial plan. Stable IDs derive from the PGO inventory key or the
instrument's primary PDF URL. Every attachment retains its municipal link label
and source-page provenance.

Excluded entries: a standalone suspension-scope map for UA VIII Can Mir and a
request for provisional-use authorization of a vehicle repair workshop. Neither
is emitted as a granted licence or a physical works project. Service descriptions,
procurement announcements, news and navigation links do not create records.

## Documents, dates and coverage limits

Live HTTP 200 PDF downloads were saved for `memoria.pdf`, the Sabadell project,
Can Mitjans statutes and bases, and the plant anteproyecto. First pages were
inspected with the preinstalled `pdftotext`. Other attachment URLs are retained
from the live inventory; their bodies were not all downloaded or parsed.

The link labelled Memòria actually opens with Programa d'Actuació, Novembre del
2002. The municipality's link title is retained as provenance, without asserting
that it is a separate or independently verified memorial document. The inventory
also labels norms Novembre 2008: neither edition label is an approval date.

The Can Mitjans PDF headers identify initial decree 2019DECR000306 (27 March
2019) and definitive decree 2019DECR000628 (27 June 2019). The Sabadell document
has an initial-approval decree 2019DECR000748, author signature and printing
timestamps. This adapter parses HTML inventory metadata only, not PDF approval
headers. Consequently `fecha`, `fecha_publicacion`, `fecha_acuerdo`, and
`fecha_aprob` remain null. Printing, signature, document-edition and crawl times
are never substituted for publication or agreement dates. These PDF observations
are research evidence, not hardcoded runtime metadata.

The map PDFs and technical documents may support future geometry work; this
adapter does not extract georeferenced geometry, convert drawings to points or
use a municipal centroid. Snapshot presence under Planejament vigent does not
establish construction progress or exhaustive/current legal consolidation.

## Validation and local evidence

Command:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_viladecavalls -v`

Five parser/manifest tests passed: grouping and provenance; null date/geometry
semantics; rejection of changed, paginated and unsupported-host content; stable
IDs; and disabled licences without network requests. Fixtures are inline and do
not depend on local evidence or live network access.

A real live `load_manifest` → `load_portal_adapter` → `backfill_proyectos` run
returned four records, with attachment counts 13/1/2/1. The registry's entity-policy
annotation completed with status ok but classified all four as unknown; no
housing/project subtype beyond the source evidence is asserted.

Local, uncommitted evidence under `evidence/` includes `proyectos.jsonl`,
`validation.json` (live count, source URLs, limitations, test result and PDF
caveats), the fetched HTML and five PDF captures. No shared source or dependencies
were modified, and no deployment, database or publication operations were used.
