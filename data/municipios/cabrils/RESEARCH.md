# Cabrils — INE 08030, Barcelona, Catalunya

Verified live on 2026-11-08 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One real current planning instrument is extractable. Coverage is deliberately
partial: the municipal current-POUM document inventory, not all urban planning,
public works, amendments or granted licences. `publication_ready` is false because
no verified project geometry is extracted. Scheduling and coordinate jitter are
disabled; licences are disabled.

## Official source discovery

- Municipal current inventory:
  https://www.cabrils.cat/ajuntament/normativa-municipal/poum — HTTP 200.
  The page explicitly identifies the documentation as the POUM currently in force.
  It lists 26 attachments: five reports/memoranda, norms and two annexes, and
  eighteen plans/economic-agenda documents. They all belong to one POUM and are
  retained as one record's `documentos`, including each exact source label and URL.
- Official transparency discovery page:
  https://seu-e.cat/ca/web/cabrils/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  — HTTP 200, links to `https://www.cabrils.cat/poum/`. The current municipal URL
  above was independently discovered and fetched. The transparency page is a
  discovery pointer, not an additional planning record.
- Principal attached norms:
  https://www.cabrils.cat/media/repository/POUM/Normes_urbanistiques.pdf
  — HTTP 200; downloaded 11,902,584 bytes and verified `%PDF-1.7` signature.
  This capture corroborates document availability; PDF contents are not parsed by
  this adapter, and the other 25 attachment targets were not individually fetched.
- https://www.cabrils.cat/serveis-i-tramits/tramits-i-gestions/planejament-general-modificacio.html
  is an application procedure, excluded from records.
- https://www.cabrils.cat/actualitat/noticies/ple-ordinari-29-01-2026.html
  contains an agenda item concerning PAU-2 Cal Gras 2, expediente 2285/2024.
  An agenda is not proof of approval; this amendment is outside this adapter's
  single current-plan inventory. Its dates/status are not transferred to the POUM.

Search results also include Cambrils (a different municipality), procurement
lists, and a Cabrils staff-selection practical examination describing hypothetical
works/licences. None are accepted as genuine Cabrils project records. The matching
name alone is insufficient evidence. No granted-licence inventory was verified.

## Extraction and semantics

The adapter requests the current municipal inventory via HTTPS with a timeout,
checks the final URL and content type, and reads at most 2 MB, failing rather than
truncating an oversized response. It requires the POUM heading, the explicit
current-plan narrative within `.ddbbtext`, and the principal norms attachment.
Every attachment in that content block is retained, with duplicate URLs grouped
and alternate source labels preserved. Unexpected links or pagination raise an
error. The reviewed page has no pagination; no attachment-count cap is imposed.
Update refreshes the whole single-plan snapshot; it does not use a date cutoff.

Stable record identity comes from the canonical municipal inventory URL. `fase`
is `vigente`, reflecting the inventory statement, without inventing an approval
stage or date. The page's `Darrera actualització: 26.10.2026 | 09:29` is represented
only as `fecha_actualizacion_fuente: 2026-10-26`. `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, and `fecha_aprob` remain null. File names, server timestamps and
crawl time are not substituted for legal dates. The title identifies the named
municipal POUM; no expediente number is inferred.

Coordinates and geometry remain null. Linked PDF plans may contain spatial
information, but are not converted into geometry here; no municipal centroid or
jitter is substituted. Source provenance is retained at record and document level.
Document labels are retained verbatim, including the municipal page's assignment
of letters/nucleus labels to individual plan files. No inferred correction is made.

## Validation and local evidence

`python -m unittest municipio.test_cabrils -v` with the runtime above: **6 passed**.
Checks cover grouping more than 80 attachments without a cap, duplicate links,
stable identity, document provenance, date separation, missing geometry,
rejection of forms/navigation/changed content, rejection of pagination/unreviewed
links, manifest loading through the registry, snapshot refresh and disabled licences.

Live extraction used `load_manifest('cabrils')`, `load_portal_adapter(manifest)`
and `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, including the existing
shared entity-policy annotation. Result: **1 live record, 26 document links**.
The policy reports the planning instrument's category as unknown; it does not
supply a physical-work classification or verified geometry.

Local, uncommitted evidence:

- `evidence/proyectos.jsonl`: actual live record.
- `evidence/validation.json`: live count, source URLs, limitations and test result.
- `evidence/poum.html`: exact inventory used by the extraction.
- `evidence/transparencia.html`: official discovery pointer capture.
- `evidence/Normes_urbanistiques.pdf`: corroborating principal-document capture.

Only the four requested source files were added. No dependency/shared-source
changes, credentials, databases, deployment tools or git mutations were needed.
