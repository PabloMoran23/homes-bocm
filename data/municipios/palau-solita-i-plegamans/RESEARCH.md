# Palau-solità i Plegamans — INE 08156, Barcelona

Verified live on 2026-11-07 using the preinstalled Python 3.12 environment.
The adapter extracts **26 real instruments/projects with 55 distinct document
links within their groups**, from two official municipal inventories. Coverage
is partial at municipality level. It does not establish granted building licences,
construction completion, or map geometry. Scheduling and licence extraction are
disabled; missing coordinates are never replaced with a centroid or jitter.

## Official inventories discovered

- Municipal urbanism/service index:
  https://www.palauplegamans.cat/ca/serveis/un-poble-sostenible/theme46
  (legacy `/thm46/serveis/un-poble-sostenible.htm` redirects here). HTTP 200.
  Links to POUM, derived planning/management/urbanisation, public-space actions,
  a project-map PDF and licence application procedures. Application procedures
  are not evidence of granted licences. News and procurement are not inputs.
- POUM and modifications: https://www.palauplegamans.cat/ca/poum — HTTP 200.
  **11 records:** the base POUM plus 10 modifications, including the final Can
  Valls RPUC link. There is no pagination in this inventory.
- Derived planning, urbanisation and reparcelation:
  https://www.palauplegamans.cat/ca/planejament-derivat-gestio-urbanistica-i-projectes-d-urbanitzacio
  — HTTP 200. **15 records:** three derived plans, seven urbanisation/physical
  works projects and five reparcelation projects. All three sections are parsed;
  no pagination observed. The legacy `/pag1159/` municipal link redirects here.
- https://www.palauplegamans.cat/ca/consulta-el-planejament-vigent is also indexed
  by the official website, but describes legacy 1979/1988 general planning.
  The explicit current POUM page above takes precedence. This older page is
  discovery context, not an additional current-plan record.

The public-space actions map and separate project-map PDF are outside this
adapter's coverage. It is not an exhaustive works register, historical record of
all planning proceedings, or full RPUC catalogue. Neither source provides a
verified granted-licence inventory.

## Identity, grouping and provenance

The current POUM links to official RPUC dossier
https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/233866.
The numeric RPUC identifier is stored as `rpuc_id`, not invented as a municipal
expediente. Can Valls retains its separately linked RPUC dossier 297476.
Other stable IDs hash instrument titles, rather than invent administrative
references. The PU, PR and PMU for the same area are distinct instruments.

POUM modifications are grouped by their parent list entry. Derived inventory
records follow the municipal instrument headings, retaining their complete lists
of linked volumes, plans, memoranda, annexes and notices in `documentos`.
Each document retains its source page and every label for its URL. The municipal
habitatge-assequible entry labels the same PDF as both plans and a DOGC notice;
this conflict is preserved rather than silently corrected. Split anchor labels
and duplicate links in the derived inventory are retained under one document.
The four municipal Google Drive links for Avinguda Catalunya remain one project.
Linked document contents and Drive/RPUC access were not comprehensively fetched
or parsed; these are provenance links, not a claim of downloaded full dossiers.
Base POUM documentation and plan collections remain linked collections.

The SUD 05 / PMU 03 consultation-only entry is excluded; a consultation notice
alone does not establish a technical project. The genuine related POUM
modification remains included. The Cooperativa group is titled as a licence
suspension on the site, but contains a real POUM modification, technical document
and justificatory annex: it is emitted as that modification, never as a licence.
The Industria/Catalunya urbanisation project has an explicit inventory heading
and an initial-approval notice; its following “MEMORIA I PLÀNOLS” text has no
hyperlink. The available notice is retained and the missing technical-document
link is a coverage limitation. It is not a procurement record.

## Date semantics and geometry

The base plan's definitive approval is **2015-04-23** and DOGC publication is
**2015-10-30**, as explicitly stated in the municipal narrative. The provisional
approval of 2015-03-26 is not substituted for definitive approval. PMU Camí Reial
and Can Llonch have explicitly stated municipal definitive agreements of
**2022-09-29**. The article 386 Riera de Caldes amendment's linked document label
states definitive CTUARC agreement **2024-07-12**. Publication labels explicitly
supply **2023-10-17** for habitatge assequible and **2021-09-08** for Cooperativa.
Most other dates/phases stay null. No filename dates, page update dates or crawl
dates become agreement/approval/publication dates. `fecha` remains null.

No verified instrument coordinates/vector geometry are extracted. `lat`, `lon`
and `geometry` remain null, `publication_ready` false. The common entity policy
currently classifies all 26 rows as `pendiente` and reports
`adapter_incident / unknown_entity_spike`: its eligibility rules require source
references or supported catalogue identities which these HTML inventories do
not supply consistently. This downstream classification limitation is preserved
in evidence; no municipal expediente numbers or eligible flags are fabricated
to bypass it. Extraction readiness does not imply publication eligibility.

## Retrieval and validation

The municipal server omits the Sectigo OV R36 intermediate certificate. Normal
TLS validation initially fails in this environment. On that specific failure,
the adapter retrieves the public intermediate from the certificate's Sectigo AIA
URL and checks its pinned SHA256
`6542d176bed50f193c0ce297ae44ecd8a0a86bec2ede682769344059b4e78530`.
It then validates municipal hostname and certificate chain using system roots;
TLS verification is never disabled. The intermediate is not a new trust root.
Certificate rotation may require reviewing the pin. Captures include the public
certificate bytes, not credentials.

Each inventory has a 40-second timeout and a 2 MB response limit. Unknown POUM
list entries, missing sections, orphan documents, duplicate identities, and
introduced pagination fail rather than silently truncate. Update performs a
complete snapshot refresh; there is no arbitrary record/page limit. Output is
written only after both pages parse successfully.

Validation commands:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_palau_solita_i_plegamans -v
```

Eight offline tests pass: grouped documents and dates, absent definitive date
with provisional date present, filename-date exclusion, navigation/login
rejection, unexpected groups/pagination, derived groups/consultation exclusion,
missing sections/orphan documents, snapshot stability and disabled licences.
A separate live run loaded the manifest through `load_manifest` and
`load_portal_adapter`, then called `backfill_proyectos` with local capture output.
It emitted 26 records (11 + 15), without fabricated coordinates.

Local uncommitted evidence: `evidence/proyectos.jsonl`,
`evidence/proyectos.entities.json`, `evidence/validation.json`, both live HTML
captures, discovery HTML and the public intermediate certificate. No shared
source/dependency changes, git writes, publishing or deployment operations.
