# El Poble Nou de Benitatxell / Benitachell (03042, Alicante)

Verified on 2026-11-09 with the preinstalled municipal-batches Python runtime.
This adapter implements a partial municipal planning-document inventory. It does
not claim exhaustive planning history, public works coverage or granted licences.

## Official source discovery

- [Urbanisme i obres](https://elpoblenoudebenitatxell.com/va/arees/urbanisme-i-obres/)
  is the municipal department page, linked from the council navigation. Its
  document grids expose structural maps (OE), detailed maps (OP), a synthesis,
  consolidated planning rules and a separate interpretative criterion. The live
  planning grids declare `data-nav.enabled=false` and `posts_per_page=-1`.
  All matching links are read, with no page count or record limit. Changed
  pagination causes an error rather than a partial successful extraction.
- [PGOU](https://elpoblenoudebenitatxell.com/va/arees/pgou/) was also fetched and
  captured locally. It currently contains an old press-link collection about a
  proposed structural plan and trails, rather than an authoritative document
  inventory or evidence of final approval. It is not ingested as another plan.
- The department links to the [electronic office](https://benitatxell.sedelectronica.es/info.0)
  and individual application procedures. Those links and the downloadable licence
  forms are service entry points, not records of licences granted. The adapter
  does not enumerate that office, the transparency portal or procurement.

## Records and provenance

1. **Normas Subsidiarias — texto consolidado**: one instrument record containing
   17 documents: five OE links, ten OP links, the synthesis and consolidated rules.
   Each retains its exact title, URL and referring inventory URL; the two Drive
   map links are preserved as published. Map sheets are not separate projects.
   [Synthesis PDF](https://elpoblenoudebenitatxell.com/wp-content/uploads/2025/12/1.1-Document-de-sintesi_Benitachell-V05_signat_signed.pdf)
   and [consolidated rules PDF](https://elpoblenoudebenitatxell.com/wp-content/uploads/2025/12/1.2-NN-UU-Text-Consolidat_Benitatxell-V05_signat_signed.pdf)
   are fetched and checked for the instrument name. The synthesis identifies a
   consolidation of existing instruments without normative changes. Its opening
   diligence refers to November 2022, with December 2022 signatures; these are
   not treated as a new plan approval. Historic plans discussed inside this
   synthesis are not emitted as independently verified records.
2. **Cumbre del Sol interpretative criterion**, expediente **1237/2024**:
   a separate planning interpretation, not a building project or licence.
   The [municipal certificate PDF](https://elpoblenoudebenitatxell.com/wp-content/uploads/2025/12/CRITERIO-INTERPRETATIVO-NORMATIVA-PP-CUMBRE-DEL-SOL-USOS-TERCIARIOS-ZONA-OLIVOS-PUEBLO-DEL-MAR.pdf)
   includes the plenary certificate and supporting material. On PDF page 1 the
   table explicitly identifies the Pleno session as **13/05/2024**. The parser
   extracts this dynamically into `fecha_acuerdo`, with page and field provenance.
   A supporting signature dated 09/05/2024 is not substituted for the agreement.
   The PDF and all its constituent pages remain together in one document link.

`fecha`, `fecha_publicacion` and `fecha_aprob` remain null. The 2025/12 upload
paths and page update dates do not establish publication or approval dates.
The current inventory does not establish that the 2022 consolidation includes
all subsequent amendments. No coordinate system or project footprint was
verified: geometry and coordinates are null, and `publication_ready=false`.
No municipal-centre point or jitter is used. Unknown entity-policy classification
is retained for review rather than changing shared categorisation rules.

## Implementation and validation

The manifest follows `municipio/manifest.py` and the existing adapters, using
`AyuntamientoAdapter` and the dynamic registry spec. No shared source or dependency
files change. Existing `requests` and BeautifulSoup parse the inventory;
preinstalled `/usr/bin/pdftotext` verifies the three core PDFs without installing
software. Extraction fails on missing document families, ambiguous criteria,
unverified certificate text, HTTP failures, non-PDF core downloads or changed
pagination. Output replacement occurs only after the entire extraction succeeds.
Updates refresh the same complete inventory without a date watermark. Licences
are explicitly disabled, and both licence methods report that status.

Executed:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_el_poble_nou_de_benitatxell -v
```

Five offline tests cover grouping/deduplication, form exclusion, pagination,
missing/foreign source links, agreement versus signature date, invalid PDFs'
semantic text, and preservation of prior output on failure. A real extraction
was then run through `load_manifest`, `load_portal_adapter` and
`backfill_proyectos`, including the shared entity-policy annotation. It produced
**2 records** with document counts **17 and 1**.

Local, uncommitted evidence under `evidence/`:

- `proyectos.jsonl`: actual live adapter output.
- `validation.json`: live record count, fetched source URLs, limitations and result.
- `urbanisme.html`, `pgou.html`: official inventory/discovery captures.
- `document-1.pdf`, `document-2.pdf`, `document-3.pdf`: the three verified core PDFs;
  corresponding `.txt` files were generated during research.

Map URLs are retained but their files are not downloaded or interpreted. This is
not a full census of the council website or electronic-office notices. Schedules
remain disabled, and no publication or deployment action is performed.
