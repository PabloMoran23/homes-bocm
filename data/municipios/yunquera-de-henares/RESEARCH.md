# Yunquera de Henares — Guadalajara — INE 19331

Verified 2026-11-09 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
The adapter implements a current snapshot of the **published inventory**, not a
claim that its historic dossiers remain open or that every instrument is in force.
Five real planning/project groups retain all 25 document links. Coverage of the
municipality is partial. Licences, scheduling and coordinate jitter are disabled.

## Discovery and official inventories

- [Municipal website](https://www.yunqueradehenares.com/) and
  [Normativa Municipal](https://www.yunqueradehenares.com/normativa-municipal/)
  link the official electronic headquarters and transparency portal. HTTP 200.
- [Transparency root](https://yunqueradehenares.sedelectronica.es/transparency)
  exposes public folders through Wicket GET navigation. Following the public
  callback without AJAX headers redirects to stable UUID folder URLs. Only an
  anonymous session is used; no login or credentials.
- [7. Urbanismo, obras públicas y medio ambiente](https://yunqueradehenares.sedelectronica.es/transparency/175e1f74-8652-404b-9f6d-cb7ce3fa3ea6/)
  advertises 25 documents. The current 7.2 environmental plans, 7.3 urban
  regulations, 7.4 public works/infrastructure and 7.5 indicators folders are
  empty. Their headings are not project records.
- [7.1 Planeamiento urbanístico](https://yunqueradehenares.sedelectronica.es/transparency/65b84ba4-213c-4ba1-ac4f-3eefe58eae59/)
  contains one document: modification of the confluence of Avenida de las
  Autonomías and Calle Quevedo, diligenced for public information.
- [7.6 Expedientes en información pública](https://yunqueradehenares.sedelectronica.es/transparency/66a6d96b-819b-4132-a43f-988f20abd491/)
  contains 24 documents, grouped as below. Every inventory fetch returned HTTP 200.
- The separate Normativa category advertises 16 documents under “proyectos en
  tramitación”; that category concerns normative drafting and is outside this
  adapter's physical-project/urban-planning scope. It is not used as a project feed.
  Municipal news, procurement notices, ordinance tables and the procedures
  catalogue are not treated as project or granted-licence inventories.

## Extracted groups and provenance

1. **Modificación puntual Autonomías–Quevedo**: one
   [planning document](https://yunqueradehenares.sedelectronica.es/preview-document/8e491cbb-585d-48cc-a03d-18250fad6241).
2. **Expediente 756/2020, photovoltaic project in El Rebollar**: eight documents
   in its [dossier](https://yunqueradehenares.sedelectronica.es/transparency/b8cf8b09-b48a-4197-a7f1-62993d723eab/),
   including execution and evacuation projects, applications, transfer documents
   (one says “El Rebollo”) and the public-information announcement. Source spelling
   is retained rather than resolving the discrepancy by invention.
3. **Expediente 277/2021, agricultural building/feed factory**, parcels 610 and
   841, polygon 2: seven documents in its
   [dossier](https://yunqueradehenares.sedelectronica.es/transparency/66a2ddb7-c385-45a1-8226-02ed04859b10/),
   including project report, plans, budget, conditions, safety study, urban
   qualification report and certification. The folder's reference to “ampliación
   de licencia” does not establish a granted licence for the proposal.
4. **Expediente 453/2022, photovoltaic self-consumption at Sotoblanco**, parcel
   5001, polygon 5: the two loose documents in 7.6 are one project. The
   [project dossier](https://yunqueradehenares.sedelectronica.es/preview-document/e1329d6f-8901-4608-b28b-342a213176ae)
   and [index](https://yunqueradehenares.sedelectronica.es/preview-document/76c024b6-4dd9-452b-988f-980fee4b3905)
   are grouped by their explicit expediente number.
5. **La Campiña II mining extension**, parcels 962, 963, 392–395, polygon 3:
   seven documents in its [dossier](https://yunqueradehenares.sedelectronica.es/transparency/3092a2a0-9b9c-478c-8174-7122a5f91e26/),
   including exploitation project, urban report, EIA, a document titled
   authorization resolution, announcements and secretary report. A document title
   alone does not establish municipal licence approval, approval date or present
   execution status.

Every retained document has its original title, official stable preview URL and
containing inventory URL. Supporting applications and announcements remain inside
the real project group; they do not generate separate records. Stable identities
use dossier URLs, or the document URL for the single planning instrument and
loose expediente. No guessed municipal expediente is assigned to the modification.

## Dates, geography and limitations

The inventory does not expose agreement or publication dates. All four date
fields (`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`) remain null.
The date embedded in a filename is not an approval date. The preview page's
“Fecha de creación” is document metadata, not publication or agreement.

For independent source inspection, the modification preview and its actual
18,133,452-byte PDF were captured in evidence. `pdftotext` confirms the document
is a modification of the indicated junction in Yunquera de Henares, Guadalajara.
Its diligence states a **19 October 2017 agreement to submit to public
information**; the signature is 20 October 2017, and the preview creation metadata
is 9 November 2017. These are distinct events. This inventory adapter does not
parse PDF contents and leaves its agreement field null; it never assigns these
events as definitive approval. The PDF also discusses older NNSS dates, which
must not be transferred to the modification.

The adapter extracts inventory metadata and links, not PDF bodies, administrative
histories, granted licences or regional planning-register completeness. Published
historic material does not establish current legal force. No coordinates or
project geometry are verified: lat/lon/geometry null and publication_ready false.
No municipal centroid, parcel centroid or jitter is substituted.

## Traversal and validation

Each run refreshes sections 7.1 and 7.6 and traverses every descendant folder.
Advertised recursive document counts are checked at every visited folder. Live
counts are 1 + (8 + 7 + 2 + 7) = 25 documents, yielding five instruments/projects.
There is no pager in the observed inventories. A pager, count mismatch, cycle,
unknown row, ambiguous grouping or missing inventory raises an error before
writing output; no page or arbitrary record limit is silently accepted. Fetches
have a 40-second timeout and a 4 MB HTML limit. Updates perform the same complete
snapshot and leave the incremental state file untouched.

Validation commands:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_yunquera_de_henares -v
```

Eight parser/traversal/contract tests pass, covering document grouping, separate
null dates, application-only rejection, changed pagination/count rejection,
external links, missing public inventory, stable IDs, snapshot updates and
licences disabled. A real `backfill_proyectos` run produced five records and
25 linked documents. Local `evidence/proyectos.jsonl`, `evidence/validation.json`,
HTML captures and the inspected planning PDF/text retain the verification.
Evidence is local and is not part of the four source files.
