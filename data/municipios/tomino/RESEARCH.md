# Tomiño — INE 36054, Pontevedra, Galicia

Live discovery and extraction: 2026-11-07. Adapter contract and manifest schema
reviewed in `municipio/adapters/portal.py`, `municipio/manifest.py`, the registry,
and existing Hernani, Manlleu and Chipiona examples. Only one municipality is added.

## Official inventory and scope

https://tomino.gal/area-de-urbanismo/ is the municipal department's current public
planning inventory (HTTP 200). It contains a complete, unpaginated HTML accordion
under “Plan Xeral de Ordenación Municipal (PXOM) e outros planeamentos”. All its
planning sections are processed, ending at “Trámites e Procedementos”. No page
limit or document count limit truncates extraction. Pagination markers cause an
error, as do missing boundaries, unreviewed headings, empty document blocks or
unreviewed document hosts.

Eleven real instruments, with 485 distinct links within their respective records:

| Instrument | Document links |
| --- | ---: |
| PXOM 2001, including normative documents and all three plan sections | 66 |
| M.P. 1A, public open space in Tomiño | 5 |
| M.P. 1B, protection characteristics in Vilachán | 9 |
| M.P. 2, municipal public-road inventory incorporated into PXOM | 26 |
| M.P. 4, ordinance 1-B and AR1/AR2 | 9 |
| M.P. 6, AR3 Goián | 2 |
| PEPID Altos de Torona | 19 |
| M.P. 8, public spaces and uses in Goián | 8 |
| Urbanización da AR4, Goián | 2 |
| M.P. 9, Seixo and Avenida do Baixo Miño | 1 |
| M.P. 10, Parque Agro Industrial Transfronteirizo do Baixo Miño | 338 |

Identity uses the explicit municipal instrument number/name, never the document
count or an invented dossier number. Four PXOM sections are grouped into one
record. All MP10 attachments, including its detailed sector documents, remain
in the single MP10 instrument. Missing MP numbers are not invented.

The department's licence forms, communications, examples and the segregation
service instruction 1/2024 are excluded. They are neither granted licences nor
projects. The municipal urbanism news archive
https://tomino.gal/category/urbanismo-2/ was discovered but is not used: this
adapter deliberately covers the documentary planning inventory, not all news,
procurement, municipal works, licence history or other regional inventories.

## Provenance and semantics

Each attachment retains its label, URL, original href, section title and municipal
provenance URL. PDFs and ZIPs are on the municipal uploads host; MP10 links also
point to Google Drive as explicitly published by the municipality. The adapter
retains them without accessing credentials or parsing their contents. Attachment
availability and legal contents have not been individually verified.

Some municipal links contain `http:///tomino.gal/` typos. Only this exact pattern
is repaired to `https://tomino.gal/`; the original href remains available. Other
HTTP links retain their published scheme. Link collection is not a claim that
every historical document is still downloadable or legally in force.

Only MP9 and MP10 have an explicit initial-approval heading; that phase is
retained. Other phases remain null, even where an approval attachment exists.
Publication, agreement and approval dates all remain null: neither upload paths,
filenames, the PXOM year nor crawl time supplies a verified event date.
No coordinates or vector geometry are supplied. Linked cartography is not
converted to invented points. `publication_ready` is false; scheduling, licences
and missing-coordinate jitter are disabled in the manifest.

The shared registry entity policy annotates all 11 as `pendiente`, with reason
`insufficient_identity_evidence`, and flags `unknown_entity_spike`. The inventory
has named instruments but no verified dossier references satisfying that shared
policy. This implementation does not invent expediente identifiers or alter the
shared classifier. Consequently these are real extracted review candidates,
with publication eligibility unresolved.

## Validation and reproducibility

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_tomino -v`: five passing tests cover document grouping,
  excluding forms/instructions, URL repair and provenance, explicit phase versus
  unknown dates, missing/changed inventory, pagination rejection, manifest registry
  loading and disabled licences.
- Real `load_portal_adapter(load_manifest('tomino')).backfill_proyectos(...)`
  invocation with `capture_dir` configured locally produced 11 rows / 485 links.
- `evidence/proyectos.jsonl`: actual live records and shared policy annotations.
- `evidence/validation.json`: live count, source URLs, counts per instrument,
  limitations, policy report, capture checksum and test command.
- `evidence/urbanismo.html.gz`: compressed complete live HTML source capture.
- `evidence/proyectos.entities.json`: shared classifier report.

Updates refresh the full current inventory; they do not claim a historical event
feed. Evidence remains local and is not part of the four source files.
