# Huétor Tájar — investigación portal ayuntamiento

**Municipio:** Huétor Tájar (Granada, Andalucía)  
**Slug:** `huetor-tajar`  
**INE:** 18102  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://huetortajar.org | **Operativa** — WordPress |
| Normativa municipal | https://huetortajar.org/transparencia/normativa-municipal/ | PDFs ordenanzas urbanismo/edificación |
| Normas Subsidiarias (NNSS) | https://huetortajar.org/transparencia/normas-subsidiarias/ | Memoria adaptación parcial (PDF) |
| Plan Municipal Vivienda y Suelo | https://huetortajar.org/transparencia/plan-municipal-de-vivienda-y-suelo/ | PDF 2018 |
| Sede electrónica | https://huetortajar.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://huetortajar.sedelectronica.es/board/ | **Operativa** — ~10 filas (mayoría empleo) |
| Catálogo trámites | https://huetortajar.sedelectronica.es/dossier | Requiere cookie de sesión (warm-up `/board`) |
| Obras y Urbanismo (citizen-service) | https://huetortajar.sedelectronica.es/citizen-service/84d48a70-c98d-4e64-9932-c9e6f9d38a40 | Agrupador trámites DIPGR |
| DIPGR consulta urbanística | https://huetortajar.sedelectronica.es/catalog/t/2ff44117-536e-448f-b619-b9e76063905a | Trámite informativo provincial |
| SITUA / VITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | NNSS 1998 publicadas en BOJA 2020 |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java).
- **Listado:** tabla HTML con `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** `preview-document/{uuid}`.
- **Contenido actual (sep 2026):** actas de selección de personal (ACTIVA-T JOVEN), policía local; sin licencias ni planeamiento publicados.

## WordPress — transparencia y planeamiento

- **NNSS:** revisión aprobada 1998; normativa publicada en BOJA 2020; memoria adaptación parcial en PDF (`MEMORIA-ADAPTACION-PARCIAL.pdf`).
- **Normativa reciente:** ordenanza de edificación (2025), reglamento entidades urbanísticas colaboradoras (2025-2026), PMI urbanístico (`PMIU_HUETOR-TAJAR.pdf`).
- **Plan Municipal de Vivienda y Suelo:** PDF 2018 en transparencia.
- **Nota:** la web incluye enlaces spam inyectados en el HTML (dominios externos); el adapter filtra solo `huetortajar.org` y `huetortajar.sedelectronica.es`.

## Licencias de obra

- No hay dataset municipal público de concesiones históricas.
- Trámites vía sede `/dossier` y citizen-service «Obras y Urbanismo» (licencias DIPGR Granada).
- Tablón sede para edictos puntuales (actualmente sin urbanismo).
- Ordenanza fiscal nº 15 (tasa licencias urbanísticas) y ordenanza de edificación publicadas en normativa.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Sin visor urbanístico municipal (ArcGIS/WFS) en web ni sede.
  - NNSS de 1998 solo en PDF; sin cartografía digital municipal enlazable.
  - SITUA/VITUA (Junta de Andalucía): documentación de planeamiento regional; sin campo expediente del ayuntamiento ni WFS REST queryable por código de expediente para Huétor Tájar.
- **Estrategia:** documentos son PDF/listas HTML sin georreferencia; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Tablón sin anuncios urbanísticos en el momento de la investigación.
  - Trámites DIPGR son formularios, no listados de concesiones.
  - Sin `geom_geojson` en fuentes públicas del ayuntamiento.

## Limitaciones generales

- Dossier requiere warm-up de cookies visitando `/board` antes.
- Web con enlaces spam de terceros en footer/sidebar.
- Consulta de expedientes requiere identificación.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.huetor_tajar:HuetorTajarAyuntamientoAdapter`
- Fuentes: tablón sede + transparencia WordPress (normativa, NNSS, PMVS) + trámites dossier + SITUA.
- IDs: `huetor-tajar-lic-*` / `huetor-tajar-proy-*` (sha256[:14]).
