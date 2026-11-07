# Capdepera — INE 07014, Illes Balears

Verified live on 2026-11-07 using the preinstalled batch venv. Two genuine
planning instruments are extracted. This is partial planning coverage, not a
municipal works census or a granted-licence register. Scheduling, licence
extraction and coordinate jitter are disabled. No geometry is inferred.

## Official source discovery

The current municipal [Urbanisme department](https://ajcapdepera.net/ca/gestio-del-territori/urbanisme)
links to planning material but its downloadable licence items are application
forms, not grants. Those are excluded.

The [public Urbanisme inventory](https://ajcapdepera.net/ca/enllacos/urbanisme)
contains six folders and a BOIB link. All folders and nested detail links were
visited during live extraction, with HTTP 200:

- `planejament-modificacio-de-nnss`: two nested folders,
  `modificacio-costa-canyamel` (empty) and `vial-font-de-sa-cala-ctra-coves`.
- The vial folder links to `document-previ` (empty detail) and
  `modificacio-de-les-normes-subsidiaries`, both below
  `/ca/enlla%C3%A7os/vial-font-de-sa-cala-ctra-coves/`.
  The latter explicitly identifies **Modificació 2/2013 de les Normes
  Subsidiàries del Terme Municipal de Capdepera**, concerning the connection
  between Font de Sa Cala and Carretera de Ses Coves. This named instrument is
  one record; no date, approval, execution or phase is claimed. Its detail text
  has no downloadable technical files. The empty preliminary page is not evidence
  of a second instrument or a substantive document.
- `unitat-actuacio-son-moll-dabaix` exposes “Son Moll 1” and “Son Moll 3”,
  pointing to `http://libre/www.ajcapdepera.net/son-moll-1.pdf` and the equivalent
  `son-moll-3.pdf`. The host `libre` is invalid for a public official source;
  no guessed replacement URL, record or approval is emitted.
- `quotes-cala-gat`, `quotes-cala-gat-0`, `normes-subsidiaries`, and
  `unitat-dactuacio-zona-oest-del-sector-8` have empty content. Folder names alone
  are not treated as substantiated instruments.

The municipality links directly to the
[BOIB consolidation agreement and full text](https://www.caib.es/eboibfront/ca/2020/11238/637516/acord-de-la-comissio-insular-d-ordenacio-del-terri).
The adapter preserves this municipal provenance and groups the HTML and
[authentic PDF](https://www.caib.es/eboibfront/pdf/ca/2020/138/1065027)
in one NNSS consolidation record. The PDF was fetched successfully and captured
locally, with its PDF signature verified.

The agreement is dated **2020-04-24**; publication in BOIB 138 is **2020-08-08**.
The agreement gives conformity to a consolidation and explicitly says it does
not constitute definitive approval of a planning instrument. Accordingly,
`fecha_acuerdo` and `fecha_publicacion` are separate; `fecha_aprob` is null.
The narrative also mentions the underlying NNSS approval of 1986-03-14 and
municipal plenary approval of the consolidated text on 2019-12-05. Neither is
substituted for the 2020 agreement, publication or definitive approval date.
Generic `fecha` is null. No crawl time or year in an instrument number is used
as an event date.

## Extraction and limitations

The adapter traverses the public planning taxonomy and detail links, including
all exposed pager links, deduplicating visited URLs. No page limit or silent
truncation is used; the live inventory exposed no pagination. Responses over
5 MB, HTTP errors, changed hosts or missing main markup fail extraction before
replacing an existing output. Consolidation requires explicit Capdepera title,
conformity narrative and official PDF provenance. Instrument IDs derive from
source URLs. Update refreshes the same complete inventory snapshot.

One record groups the consolidated NNSS documents; the vial modification is
separate. Mere navigation, forms, procurement notices, unrelated news and empty
folders do not become records. Other planning registers, environmental dossiers,
municipal news and contracting portals are outside this implementation's scope.
The inventory's continued availability does not prove that it includes every
current modification or project, nor that any physical works have commenced.

No instrument coordinates or geometry were verified. `lat`, `lon`, `geometry`
are null and `publication_ready` is false. The existing shared entity policy
classifies both rows as `pendiente`, with `insufficient_identity_evidence` and
`activity_eligible=false`; these planning records are not asserted to be
activity or licence grants. No shared policy changes were made.

## Validation and evidence

Run from the workspace:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_capdepera -v
```

Six tests pass: distinct agreement/publication semantics and grouped documents;
missing dates; exclusion of forms, empty folders and login shells; named
modification identity; complete mocked pagination and stable snapshot refresh;
and preserving previous output on source failure.

Live extraction used `load_manifest('capdepera')`, `load_portal_adapter`, and
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, with `capture_dir` set
locally to `evidence/captures`. It produced **2 records** across 12 fetched HTML
source URLs. The authentic PDF was additionally downloaded. Local evidence:
`evidence/proyectos.jsonl`, `evidence/validation.json`, HTML captures and
`evidence/nnss-boib.pdf`. Validation records all source URLs, live count, limits
and shared policy output. Evidence is local and is not source to commit.
