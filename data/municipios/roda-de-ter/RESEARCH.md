# Roda de Ter — Barcelona — INE 08183

Verified live on 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One adapter, deliberately partial planning-instrument coverage. Scheduling,
licences and missing-coordinate jitter are disabled. `publication_ready` is false.

## Official source discovery

- [Urbanisme](https://www.rodadeter.cat/ajuntament-seu-electronica/informacio-oficial/16-urbanisme)
  links to planning, urban management and projects in process. Application forms
  in its navigation are not evidence of granted licences.
- [Planejament urbanístic](https://www.rodadeter.cat/ajuntament-seu-electronica/informacio-oficial/16-urbanisme/planejament-urbanistic)
  links to POUM, modifications and TUC.
- [Modificacions del POUM](https://www.rodadeter.cat/ajuntament-seu-electronica/informacio-oficial/16-urbanisme/planejament-urbanistic/modificacions-del-poum)
  is the implemented source: HTTP 200, one unpaginated HTML table containing five
  actual instruments, numbered 4, 6, 1, 2, 3, and five technical PDF documents.
  The introductory paragraph links amendments 1, 2 and 3 to RPUC dossiers 283998,
  285320 and 291351 respectively. Those links are attributed by their visible
  amendment numbers and grouped with the matching PDF, never emitted separately.
- [POUM](https://www.rodadeter.cat/ajuntament-seu-electronica/informacio-oficial/16-urbanisme/planejament-urbanistic/poum)
  returned an RPUC application shell, not instrument detail HTML. Not extracted.
- [TUC](https://www.rodadeter.cat/ajuntament-seu-electronica/informacio-oficial/16-urbanisme/planejament-urbanistic/trama-urbana-consolidada-tuc)
  redirects to the official RPUC application, dossier 265319; not extracted.
- [Gestió urbanística](https://www.rodadeter.cat/ajuntament-seu-electronica/informacio-oficial/16-urbanisme/gestio-urbanistica)
  exposes reparcelling material for PMU El Puigvell and subsector 2 of Pla Parcial
  3 l'Esquerda. This separate inventory is outside this adapter's coverage.
- [Projectes en tramitació](https://www.rodadeter.cat/ajuntament-seu-electronica/informacio-oficial/16-urbanisme/projectes-en-tramitacio)
  exposes Pont Vell rehabilitation sections 3/4 through an e-board link, and the
  street urbanisation project Verge del Sòl del Pont / Call de la Capella phase 2
  with five attached volumes/price documents. These are outside this adapter's
  coverage; they are not counted as extracted records or granted licences.

## Records and provenance

The five extracted amendments concern Puig Vell (1), industrial uses (2), carrer
de la Serra (3), material errors/wording (4), and article 136 road setbacks (6).
There is no amendment 5 in the table: numbering gaps do not authorize fabrication.
All five PDFs returned HTTP 200 with `application/pdf` and were captured locally.
The record's `url` and each document's `source_url` retain the municipal inventory
provenance; `url_documento` points to its first technical PDF. `documentos` retains
all distinct links, including the three RPUC references. RPUC IDs are register
identifiers, not asserted municipal expediente numbers.

Only amendments 4 and 6 explicitly say `aprovació inicial` in the table. Their
`fase` is initial approval of the linked document, without an invented approval
date. The other stages remain null; PDF filenames do not establish legal status.
The municipal page may lag later agreements: this is an inventory of documents
currently exposed, not a certification of the latest legal status. RPUC dossiers
are preserved but not crawled. No unrelated news or procurement announcements
are scraped as projects.

The page update timestamp, 25-04-2025 19:39, is not a record publication or agreement
date. `fecha`, `fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` stay null.
No PDF-internal dates or geometries are parsed. `lat`, `lon` and `geometry` stay
null; no centroid, random point or inferred coordinate is substituted.

## Extraction and validation

The adapter uses the existing portal interface and installed requests/BeautifulSoup
libraries. A bounded 3 MB streamed response and HTTP timeouts protect the fetch.
Missing headings/table, unknown rows or document hosts, absent documents,
unattributed/conflicting register references, and pagination cause explicit
failure before replacing the output. No fixed row cap or slice truncates results.
An update refreshes the entire finite inventory. Stable IDs use municipal POUM
amendment numbers; repeated rows/documents for one instrument are grouped.

Nine parser/interface/manifest tests passed:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_roda_de_ter -v
```

A separate real `RodaDeTerAyuntamientoAdapter.backfill_proyectos` call returned
five records with eight retained document/register links. Evidence is local under
`evidence/`: `proyectos.jsonl`, `validation.json`, `modificacions-live.html`, discovery
HTML captures and five downloaded PDFs. PDF captures `modificacio-0.pdf` through
`modificacio-4.pdf` follow source-table order (amendments 4, 6, 1, 2, 3).
`validation.json` records the live count, source URLs, test result and limitations.
Evidence is not a source fixture or a file to commit. No complete municipal
history, works inventory, granted-licence register or geometry coverage is claimed.
