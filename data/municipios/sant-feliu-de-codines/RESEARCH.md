# Sant Feliu de Codines — INE 08210, Barcelona

Verified live 2026-11-09 with the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One municipal adapter; partial planning-publication history. Scheduling, missing
coordinate jitter and licence extraction are disabled. `publication_ready` is
false because these sources provide no verified instrument geometry.

## Discovery and official inventories

- Municipal Urbanisme i Mobilitat:
  https://www.santfeliudecodines.cat/temes/urbanisme-i-mobilitat/
  returned HTTP 200. Its navigation links the official transparency portal.
  The topic page is a news feed, including unrelated mobility announcements;
  it is not used as a project or granted-licence inventory.
- Municipal planning transparency entry:
  https://seu-e.cat/ca/web/santfeliudecodines/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
  returned HTTP 200 but only points to the generic RPUC application homepage,
  https://dtes.gencat.cat/rpucportal/#/inici . No instrument records are inferred
  from that generic link or the explanatory page text.
- Municipal urban-planning rules entry:
  https://seu-e.cat/ca/web/santfeliudecodines/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme
  returned HTTP 200. It identifies the exact municipality through the official
  RPUC query `municipiSel=08210` and MUC query `municipi=08210`. These legacy
  viewer links are discovery references, not extracted records or geometry.
- The geographic-information entry returned HTTP 200 without instrument links:
  https://seu-e.cat/ca/web/santfeliudecodines/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/informacio-geografica-d-urbanisme
- The territorial-plans entry returned HTTP 200 with a generic Generalitat
  territorial-planning link, not municipality-specific instruments:
  https://seu-e.cat/ca/web/santfeliudecodines/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/plans-territorials-d-urbanisme
- **Extraction inventory, official Diputació de Barcelona CIDO**:
  https://cido.diba.cat/normativa_local/6873748/planejament-urbanistic-ajuntament-de-sant-feliu-de-codines
  returned HTTP 200 with the named municipality, heading `Planejament urbanístic`,
  CIDO identifier `20170228N12`, and 19 bulletin-publication rows from 2017-02-28
  through 2025-10-16. This identifier represents the inventory, not one plan.
  The full table has no pagination controls. Its generic `Vigent` label is not
  assigned to individual plans. No claim of complete current RPUC coverage.

## Extracted instruments and grouping

The live extraction emits five real planning instruments:

| Instrument | Retained publications | Latest non-environmental publication |
| --- | ---: | --- |
| NNSS modification, passatge Costa Lloberes | 2 | 2017-03-03, initial modification |
| Special plan for biological livestock activity, Sant Miquel del Fai km 3 | 2 | 2020-01-24, initial approval |
| Rural improvement special plan, sector Granges | 4 | 2023-03-24, definitive approval |
| NNSS modification for the future C-59 bypass | 1 | 2018-02-28, definitive modification |
| NNSS modification, sector Granges | 4 | 2020-03-05, definitive modification |

Twelve distinct source publications become thirteen document associations: the
2018-07-30 notice explicitly covers both Granges instruments and is attached to
both with `relacion=publicacion_conjunta`. Reviewed Granges title variants and
`Km 3` punctuation variants are grouped. The three environmental-report notices
remain linked to their respective instruments as `informe_ambiental`. Their
CIDO action `Aprovació definitiva` does **not** set the planning phase. Six
urban-management agreement publications and one court notice are explicitly
excluded. Forms, procurement notices, businesses and unrelated news produce no
records. Unexpected instrument categories or actions fail for review.

Each document retains its original description, publication action, bulletin,
issue number, publication date, source inventory URL and valid absolute official
DOGC/BOPB links. CIDO sometimes supplies malformed relative auxiliary URLs;
these are omitted while the official bulletin links are preserved. Links are
retained exactly, including legacy query strings; future availability of all
historical documents has not been verified. The definitive Granges DOGC PDF,
`documentId=955789`, was independently fetched successfully (HTTP 200,
application/pdf, 1,217,534 bytes) and captured locally. Its contents are not
parsed or used to invent agreement dates.

`fecha_publicacion` is the latest non-environmental bulletin-publication date;
all other publication dates are retained per document. `fase` is the action
reported by that latest notice, **not** a guarantee of current legal status.
`fecha`, `fecha_acuerdo` and `fecha_aprob` stay null. No crawl timestamp, page
update date, environmental decision or bulletin date becomes an agreement date.
Coordinates and geometry remain null; no municipal centroid is substituted.

## Extraction behaviour and validation

The adapter fetches the complete inventory on backfill and update, with connect
and read timeouts and a 3 MB response limit. It verifies the municipality and
planning heading, requires valid table rows and official document URLs, rejects
empty sources and fails closed if pagination controls appear. There is no date
cutoff or row slice. Network/parser failures occur before replacing the output.

- Parser/manifest tests:
  `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sant_feliu_de_codines -v`
  — seven tests passed. Includes grouping, environmental date semantics,
  combined documents, municipality mismatch, empty/login responses, pagination,
  invalid dates, malformed links, category changes and disabled manifest flags.
- Real extraction invoked `load_manifest`, `load_portal_adapter` and
  `backfill_proyectos`, including the existing entity-policy wrapper:
  **5 live records**, 12 unique publications, 13 document associations.
  Entity policy reports all five as unknown project subtype, status ok; this
  does not establish geometry or publication eligibility.
- Local uncommitted evidence: `evidence/proyectos.jsonl`,
  `evidence/validation.json`, exact extraction response `evidence/cido-live.html`,
  discovery HTML captures and `evidence/granges-dogc-955789.pdf`. Validation
  includes source URLs, timestamp, capture hashes, counts and limitations.

Only the four requested source files are added. No shared source/dependency
changes, credentials, external workspace access, publishing or deployment.
