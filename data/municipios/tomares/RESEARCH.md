# Tomares — investigación portal ayuntamiento

**Municipio:** Tomares (Sevilla, Andalucía)  
**Slug:** `tomares`  
**Boletín:** BOJA (`boja`, 4 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.tomares.es | **Operativa** — Drupal 7 |
| Urbanismo | https://www.tomares.es/tu-alcaldia/organizacion-municipal/urbanismo | Índice planeamiento / desarrollo |
| Innovaciones PGOU | https://www.tomares.es/tu-alcaldia/organizacion-municipal/urbanismo/planeamiento-general/innovaciones-al-pgou | **8 MP** listadas en HTML (`<li>`) |
| PGOU municipal | https://www.tomares.es/tu-alcaldia/organizacion-municipal/urbanismo/plan-general-de-ordenacion-urbanistica-municipal | Enlace a SITUA Junta |
| Planes de desarrollo | https://www.tomares.es/tu-alcaldia/organizacion-municipal/urbanismo/planes-de-desarrollo | Subsecciones (estudios detalle, PE, PP) sin docs indexados |
| Sede electrónica | https://tomares.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://tomares.sedelectronica.es/board | **Operativa** — ~9 filas visibles |
| Portal transparencia | https://tomares.sedelectronica.es/transparency | Sección «7. URBANISMO…» (204 docs, AJAX) |
| Catálogo trámites | https://tomares.sedelectronica.es/dossier | Lento; sin listado histórico scrapeable |
| Consulta expedientes | https://tomares.sedelectronica.es/expedientes | Requiere Cl@ve / identificación |
| Licencias Diputación | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4109300F | Enlace oficial; portal provincial (errores intermitentes) |
| SITUA / VITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional; sin enlace por expediente ayto |
| PIC catastral | https://www.tomares.es/servicios-de-interes/existe-en-este-ayuntamiento-pic-punto-de-informacion-catastral | Punto presencial |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cártama, Cómpeta, Ronda.
- **Listado:** tabla HTML con `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** `preview-document/{uuid}`.
- **UA:** requiere User-Agent tipo navegador (`Mozilla/5.0`); `poc-bocm-*` solo devuelve 403 en `/board`.
- **Contenido actual (ago 2026):** mayoría edictos cobranza IAE/tasas residuos; pocos expedientes urbanísticos.

## Drupal — planeamiento

- **Innovaciones al PGOU:** 8 modificaciones puntuales (MP-01 a MP-11) en lista HTML sin PDFs enlazados.
- **Ejemplos:** MP-09 AO-9 «El Manchón», MP-10 permuta PAU Aljamar, MP-11 SUS-1/AO-1, ordenanzas Parque Zaudín.
- **Planes de desarrollo:** páginas de sección vacías (sin PDFs en HTML estático).
- **PGOU:** redirige consulta a SITUA (Junta de Andalucía).

## Licencias de obra

- No hay dataset municipal público de concesiones históricas.
- **Portal provincial:** Diputación de Sevilla LicytalPub con CIF `P4109300F` (enlace en web municipal).
- Trámites vía sede `/dossier` y consulta `/expedientes` (autenticación).
- Tablón sede para edictos puntuales.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Sin visor urbanístico municipal (ArcGIS/WFS) en web ni sede.
  - SITUA/VITUA (Junta de Andalucía): cartografía de planeamiento por municipio, sin campo expediente del tablón ni API WFS REST accesible para Tomares.
  - PIC catastral presencial; no API de parcelas enlazada a expedientes.
- **Estrategia:** documentos son PDF/listas HTML sin georreferencia; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Transparencia urbanismo (204 docs) requiere Wicket AJAX para subcarpetas.
  - Portal LicytalPub provincial no scrapeable de forma determinista.
  - Sin `geom_geojson` en fuentes públicas del ayuntamiento.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Transparencia: árbol de 204 docs requiere sesión AJAX; solo índice raíz scrapeado.
- Sin geometría por expediente.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.tomares:TomaresAyuntamientoAdapter`
- Fuentes: tablón sede + innovaciones Drupal + PDFs urbanismo + índice transparencia + SITUA + páginas informativas licencias.
- IDs: `tomares-lic-*` / `tomares-proy-*` (sha256[:14]).
