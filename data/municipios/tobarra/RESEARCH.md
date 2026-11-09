# Tobarra (Albacete), INE 02074

Research and live validation: 2026-11-08. The adapter extracts the municipal
**Plan de Ordenación Municipal (POM)** document inventory as one instrument.
This is partial coverage, not an exhaustive municipal project register. It does
not assert that the published POM is currently in force or definitively approved.

## Official inventories inspected

- https://tobarra.es/areas-municipales-urbanismo/ — HTTP 200. Official municipal
  urbanismo page. Six document sections: D1 M1, D2 PI, D3 MJ, D4 PO, D5 NNUU,
  D6 CAT. Contains 21 direct PDF links and two nested volume inventories.
- https://tobarra.es/urbanismo-tomo-i-ord-estructural — HTTP 200, three additional
  PDFs (cover, index, OE-1.0). All are retained in the same POM record.
- https://tobarra.es/urbanismo-tomo-ii-ord-estructural — HTTP 404 both with and
  without trailing slash during research. The original link and observed HTTP
  status are retained in `inventarios_relacionados`, and the missing volume is
  explicitly listed in `limitaciones`. No contents are guessed for this volume.
- https://tobarra.es/impresos-a-rellenar/ — HTTP 200. Application forms, including
  requests for building and first-occupation licences. These do not demonstrate
  granted licences and are excluded. `licencias.enabled` is false.
- https://tobarra.es/wp-content/uploads/2024/03/Doc3-Memoria-Justificativa.pdf —
  HTTP 200; actual POM technical document, independently downloaded to local
  evidence, with extracted text. Cover identifies Tobarra (Albacete), memoria
  justificativa, revised September 2015. Its repeated diligence text refers to
  initial approval by the municipal plenary on 05/10/2015. This is an agreement
  date for initial approval, not definitive approval or web publication. The
  adapter does not parse PDF text, so it leaves all date and phase fields null.
  The upload path `2024/03` is not used as an approval or publication date.

## Extraction contract and limitations

One stable instrument ID, `tobarra-pom`, represents the explicitly named municipal
plan, not an invented expediente number. All reachable inventory pages are walked
without pagination truncation. Current inventory: 24 unique PDF links, grouped
under that single instrument. Each document retains its original link label,
filename, section, original HTTP URL, normalized HTTPS URL and inventory page
provenance. Files whose titles are generic on the source keep those labels in
`texto_enlace`; the filename is exposed separately as `titulo`.

The municipality itself links documents over HTTP. The crawler uses HTTPS on the
same official host and preserves the original links for audit. It does not infer
records from procurement, news, application forms or menu navigation. The current
source is a static inventory, not a paginated news stream. Pagination markers
cause an error requiring review. Unexpected hosts, missing POM structure,
unusable content and HTTP errors other than explicitly reported removed nested
inventories abort the extraction before replacing any prior snapshot. A newly
linked nested inventory is traversed; exceeding the reviewed crawl bound also
raises an error instead of writing a truncated result.

The source is an inventory of documents. PDF availability is not verified for
every link on every run; the technical memoria was downloaded separately to
verify genuine planning content. The broken tomo II limits document coverage.
The adapter does not extract geometry from the plans or substitute municipal
centroids: `lat`, `lon`, `geometry` are null and `publication_ready` is false.
`schedule.enabled` and `geocode.jitter_missing` are false. Incremental update
refreshes the entire inventory snapshot; it does not claim historical completeness.

## Validation and local evidence

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_tobarra -v`: seven tests passed. Tests cover grouped
  documents, link provenance, changed source markup and forms, pagination,
  external document links, broken-volume coverage, null date/geometry semantics,
  disabled licences and preservation of the previous output on server errors.
- Live extraction uses `load_manifest('tobarra')` and `load_portal_adapter`, then
  calls `backfill_proyectos`, including the existing entity-policy wrapper.
- Local `evidence/proyectos.jsonl`: one real planning instrument; 24 document
  links; missing tomo II reported. Existing entity policy may classify this
  instrument as pending because the page supplies no expediente identifier or
  current approval act. No identifier or approval claim is fabricated to alter
  that classification.
- `evidence/validation.json`: live record count, all fetched inventory URLs,
  document URLs, limitations and test outcome. HTML captures include successful
  pages and the linked 404. `evidence/memoria.pdf` and `evidence/memoria.txt`
  preserve the separately reviewed technical document. Evidence stays local.
