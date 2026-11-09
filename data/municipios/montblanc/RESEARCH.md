# Montblanc — INE 43086, Tarragona

Research and live verification: 2026-11-09. This adapter extracts the municipal
planning inventory from the Generalitat's public RPUC, explicitly linked by
Montblanc's transparency seat. Coverage is partial: municipal general and derived
planning registered there, rather than all municipal works, pending proposals or
granted licences. Scheduling is disabled and missing coordinates remain null.

## Official source discovery

- Municipal planning index:
  https://www.montblanc.cat/serveis/urbanisme/planejament-urbanistic
  exposes a `Normativa 2025` file view, with a compiled regulation PDF. This is
  documentation, not a new project or an approval dated 2025.
- Municipal map inventory:
  https://www.montblanc.cat/serveis/urbanisme/planols-del-pla-general-i
  lists general-plan map sheets. Sheets must not become separate projects.
- Transparency planning page:
  https://seu-e.cat/ca/web/montblanc/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  links `https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=43086`.
  This redirects to the current RPUC application at
  https://planejamenturbanisme.territori.gencat.cat/rpucportal/ .
- Public application JavaScript identifies its read-only JSON endpoints under
  `/RPUC-portal/rest/consulta/`: `basica`, `detall`, `arbre`, `documents`.
  The adapter uses those current endpoints with TLS verification enabled.
- Licence application service:
  https://actio.dipta.cat/catalegserveis/id/4308620002/servei/AT089_RBANI_00003?mobile=true&origen=seu
  describes how to request a major-works licence. It is not a grant register and
  contributes no records. Procurement announcements and general news are excluded.

The municipal www site failed certificate-chain validation in both Requests'
normal trust store and the system CA bundle. An explicitly unverified research
request captured the index and file-view HTML locally; these captures are not
used by the scraper. The production extraction path uses only verified HTTPS
requests to RPUC. Search-engine results corroborated the municipal index and map
inventory, but are not extraction inputs.

## Extraction and semantics

`basica` receives municipality `43086`, language `ca`, `rpp=20`, `firstRecord=1`
onward, sorted by `tema` ascending. In the public UI `firstRecord` is a one-based
page number, not a row offset. All advertised results are traversed, including
supramunicipal entries. A changed total, empty premature page, repeated identity,
invalid identity or excess rows causes failure before replacing the output.

Only entries whose municipality is exactly `Montblanc` proceed to detail lookup;
detail ID and municipality are checked again. Only `codiRang=PG` (general) and
`PD` (derived planning) are retained. Agreements (`CNV`), TUC delimitations and
entries filed under other municipalities are excluded. An amendment with its own
RPUC dossier remains a distinct instrument; records are not merged just because
their titles resemble one another.

Each record groups the complete returned document tree under its real RPUC
identity, with document download URLs, titles, category paths and original
`portal`, `afectat`, `baixa`, `recurs` flags. Duplicate document IDs are grouped,
retaining category paths. Missing documents fail extraction. This is the current
public document tree, not a reconstruction of all historical document versions.
Register entries (`assentaments`) are retained as metadata, not emitted as projects.

`dataAprovacio` maps exclusively to `fecha_aprob`; `dataPublicacio` exclusively to
`fecha_publicacion`. Generic inventory `data` is not used to infer either date.
`fecha` and `fase` remain null: a registered/vigente flag is not a specific approval
phase. Dossier number, authority, bulletin references and source provenance are
retained. Missing dates remain null; invalid dates raise errors. Dates of register
entries and crawl time are not approval dates.

No coordinates, parcel centroids or municipal centroids are invented. Map PDFs
have not been converted into verified vector geometry. `publication_ready=false`,
`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
Updates refresh the entire snapshot; the state path is intentionally unused.

## Local validation

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Parser/integration tests: `-m unittest municipio.test_montblanc -v`.
Tests cover date meanings, absent/invalid dates, document grouping, wrong identities,
non-plan exclusions, multi-page completion, repeated/empty/changing pages and
manifest-based adapter loading with another municipality excluded.

A real extraction uses `load_portal_adapter(load_manifest('montblanc'))` with local
`capture_dir=evidence/rpuc`, then `backfill_proyectos(evidence/proyectos.jsonl)`.
Raw inventory pages, dossier details and document trees are saved under that
capture directory. `evidence/validation.json` records actual counts, all live source
URLs, entity-policy results and limitations. Evidence is local and uncommitted.

Live result: **92 planning instruments**, **524 grouped document links**, from
**102 inventory entries across six pages**. Eight entries filed under other
municipalities and the municipal agreement/TUC entries are excluded. Six tests
passed. A sample actual agreement PDF (RPUC document 47567, dossier 30050) was
fetched successfully with verified TLS and saved in evidence; it is scanned and
`pdftotext` yielded no usable narrative, so its dates were not inferred from OCR.
The dossier's explicit detail fields give approval 1998-01-28 and publication
1998-03-27. The public current-plan record does not imply construction activity.

The adapter adds the accurate category `planeamiento urbanístico` while retaining
the original Catalan typology in `tipo`. This lets the shared entity classifier
recognize real, referenced planning dossiers without translating or replacing the
source typology. The final live evidence includes the shared classification report.
