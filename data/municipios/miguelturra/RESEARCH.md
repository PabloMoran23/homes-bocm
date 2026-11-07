# Miguelturra — INE 13056, Ciudad Real, Castilla-La Mancha

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Candidate for independent review; accepted=false. Partial planning coverage only.

## Official source discovery

The municipal [transparency block 5](https://www.miguelturra.es/portaltransparencia/bloques/bloque5)
links its POM, maps, modifications and urban regulations to
[Normas Urbanísticas](https://www.miguelturra.es/ayuntamiento/normas-municipales/normas-urbanisticas).
Both returned HTTP 200. The public-works/project and works-monitoring rows in
that transparency block display ACCEDER without usable links. These empty rows
are not projects. No granted-licence inventory was verified; licences are disabled.
No procurement announcements, employment material or unrelated news are ingested.

The current HTML inventory contains eight fiches, with no pager. Seven identify
planning instruments or a POM correction. They produce six records after grouping:

- [POM 2007](https://www.miguelturra.es/ordenanzas/plan-ordenacion-municipal-2007),
  with its main PDF and the separately published
  [March 2008 correction](https://www.miguelturra.es/ordenanzas/correcion-errores-pom-marzo-2008).
  The correction PDF explicitly identifies errors in the published POM norms;
  it is attached to the same plan with its own source-fiche provenance.
- [January 2009 modification](https://www.miguelturra.es/ordenanzas/modificacion-puntual-pom-enero-2009).
- [February 2010 modification](https://www.miguelturra.es/ordenanzas/modificacion-puntual-pom-febrero-2010).
- [June 2012 modification](https://www.miguelturra.es/ordenanzas/modificacion-puntual-pom-junio-2012).
- [Modification 7/2018](https://www.miguelturra.es/ordenanzas/modificacion-puntual-plan-ordenacion-municipal-numero-72018-bop-2025-08-28).
  Its body explicitly identifies definitive approval in the commission session of
  **2018-07-31**. The title explicitly identifies **BOP publication 2025-08-28**;
  these dates are stored separately, with the supporting text and source URL.
  The narrative also mentions DOCM publication on 2018-12-04, which remains in
  the source description rather than replacing the BOP publication field.
- [Modification 8](https://www.miguelturra.es/ordenanzas/modificacion-puntual-numero-8-plan-ordenacion-municipal).
  This fiche describes public consultation under decree 2022/150 of **2022-02-15**,
  with an attached technical/plans document. This is a real planning instrument,
  not a granted licence. The announcement date 16/02/2022 is not asserted as its
  publication date. The adapter does not claim definitive approval or present-day
  procedural status from this historical public-consultation fiche.

The eighth fiche,
[Granátula parcel norms](https://www.miguelturra.es/ordenanzas/normas-urbanisticas-referentes-parcelas-calle-granatula-2026-09-21),
is deliberately excluded. Its PDF cover says “NORMATIVA APLICABLE DERIVADA DEL
ESTUDIO DE DETALLE” for parcels on Granátula, Carrión and Avenida Descubrimientos.
The HTML does not identify a separate study-of-detail expediente or approval.
It remains captured as discovery evidence, without inventing an independent
instrument from a parcel norms sheet. This exclusion makes coverage partial.

## Extraction contract and limitations

The adapter parses the scoped Drupal `.view-ordenanzas` inventory, then each
supported instrument's `article.node` title, body and file-attachment field.
It retains every attachment under `documentos`, with link labels and source-fiche
URLs. Images, footer links and recent-news teasers are outside this selection.
Stable record IDs derive from official instrument URLs. POM corrections retain
both their document and fiche link on the POM record. Each modification has its
own identity; these are distinct legal instruments, not duplicate PDF records.

All inventory pager links are followed and deduplicated. Unsupported pagination,
missing structure, empty inventories, wrong titles, missing documents, external
URLs, failed requests and unexpected redirects raise errors. The 100-page safety
limit raises before output, never silently truncates. A successful update replaces
the complete snapshot atomically; it is not a historical change log. HTML source
captures are optional through adapter config `evidence_dir`.

Only explicit labelled HTML dates are parsed. Years/months in titles, filenames,
PDF metadata, crawl timestamps and footer dates are not approval dates. The PDF
captures were checked for successful PDF responses and retained locally; PDF text
is not parsed by the adapter. No completeness or current validity claim is made
beyond the published municipal inventory. The adapter does not query a regional
planning register or an authenticated expediente system.

No project geometry was verified. Coordinates and geometry remain null;
publication_ready=false. The town-hall Google Maps footer location is not used as
project coordinates. `schedule.enabled=false`, `geocode.jitter_missing=false`, and
`licencias.enabled=false` are explicit in the manifest.

## Reproduction and local evidence

Run from the repository root:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_miguelturra -v
```

Seven parser/adapter tests pass, covering date separation, public-consultation
semantics, correction grouping/provenance, invalid sources, excluded non-project
content, full pagination traversal, manifest loading and disabled licences.

A real `MiguelturraAyuntamientoAdapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`
run fetched the inventory and all seven supported fiches: **6 live records**, 7
linked PDFs, one inventory page. Local `evidence/validation.json` records the
runtime, result, source URLs, count and limitations. Local evidence also contains
HTML captures of the inventory, transparency page and all eight fiches, and all
eight linked PDFs (including the excluded Granátula sheet). These evidence files
are local review artifacts and are not source changes to commit.

No shared source files or dependencies were changed. No credentials, other
workspaces, databases, deployment, publishing, git mutations or remote code hosts
were used.
