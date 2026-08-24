# Alcalá de Guadaíra — investigación portal ayuntamiento

**Municipio:** Alcalá de Guadaíra (Sevilla, Andalucía)  
**Slug:** `alcala-de-guadaira`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.alcaladeguadaira.es | **Operativa** — CMS propio PHP |
| Urbanismo | https://www.alcaladeguadaira.es/servicios-municipales/urbanismo-y-planificacion-estrategica | Índice departamento |
| PGOU-94 vigente | https://www.alcaladeguadaira.es/servicios-municipales/urbanismo-y-planificacion-estrategica/ordenanzas-y-normativas/16/1-planeamiento-general-vigente-pgou-94-y-modificaciones | **~140 PDFs/planos** en `/contenidos/downloads/ordenanzas/` |
| Revisión PGOU-94 | https://www.alcaladeguadaira.es/servicios-municipales/urbanismo-y-planificacion-estrategica/ordenanzas-y-normativas/16/2-revision-del-pgou-94 | Documentación revisión + enlace portal participación |
| Modelos trámites | https://www.alcaladeguadaira.es/servicios-municipales/urbanismo-y-planificacion-estrategica/modelos-de-solicitud-tramites-urbanismo | Formularios licencias/DR (PDF/DOC) |
| Portal revisión PGOU | https://plangeneral.alcaladeguadaira.es/documentacion/ | WordPress — plan vivienda, prediagnóstico |
| Sede electrónica | https://ciudadalcala.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://ciudadalcala.sedelectronica.es/board | **Operativa** — ~10 filas visibles |
| Portal transparencia | https://ciudadalcala.sedelectronica.es/transparency | Sección «INFORMACIÓN ESPECÍFICA SOBRE URBANISMO Y MEDIO AMBIENTE» (25 docs, AJAX) |
| Catálogo trámites | https://ciudadalcala.sedelectronica.es/dossier | Procedimientos telemáticos URDROM |
| Consulta expedientes | https://ciudadalcala.sedelectronica.es/expedientes | Requiere Cl@ve / identificación |
| SITUA / VITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional; sin enlace por expediente ayto |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Tomares, Conil, Enguera.
- **Listado:** tabla HTML con `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** `preview-document/{uuid}`.
- **Contenido actual (ago 2026):** información pública calificación/licencia ambiental de actividades; anuncios estatales/autonómicos; pocos expedientes urbanísticos propios.

## Web municipal — planeamiento

- **PGOU-94 vigente:** texto refundido, normas urbanísticas, planos de calificación, alineaciones y gestión del suelo (PDFs estáticos).
- **Revisión PGOU-94:** proceso en curso con portal participación `plangeneral.alcaladeguadaira.es` (WordPress).
- **Modelos trámites:** licencias de obra, declaraciones responsables, comunicaciones previas (formularios descargables; trámites telemáticos en sede).

## Licencias de obra

- No hay dataset municipal público de concesiones históricas.
- Trámites vía sede `/dossier` (procedimientos URDROM) y consulta `/expedientes` (autenticación).
- Tablón sede para edictos puntuales (licencias de actividad, información pública ambiental).
- Modelos presenciales en web municipal; personas jurídicas obligadas a sede electrónica.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Sin visor urbanístico municipal (ArcGIS/WFS) en web ni sede.
  - SITUA/VITUA (Junta de Andalucía): cartografía de planeamiento por municipio (PGOU-94), sin campo expediente del tablón ni API WFS REST accesible para expedientes individuales.
  - Planos PGOU en PDF raster sin georreferencia vectorial enlazable.
- **Estrategia:** documentos son PDF/listas HTML sin georreferencia; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Transparencia urbanismo (25 docs) requiere Wicket AJAX para subcarpetas.
  - Sin `geom_geojson` en fuentes públicas del ayuntamiento.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Transparencia: árbol de 25 docs requiere sesión AJAX; solo índice raíz scrapeado.
- Sin geometría por expediente.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.alcala_de_guadaira:AlcalaDeGuadairaAyuntamientoAdapter`
- Fuentes: tablón sede + PDFs urbanismo web + portal revisión PGOU + índice transparencia + SITUA + páginas informativas licencias.
- IDs: `alcala-de-guadaira-lic-*` / `alcala-de-guadaira-proy-*` (sha256[:14]).
