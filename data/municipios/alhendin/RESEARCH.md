# Alhendín — investigación portal ayuntamiento

**Municipio:** Alhendín (Granada, Andalucía)  
**Slug:** `alhendin`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 18014

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://alhendin.es | **Operativa** — WordPress 5.9 + Yoast SEO |
| Sede electrónica | https://alhendin.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://alhendin.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://alhendin.sedelectronica.es/dossier | **Operativa** (lento en CI) |
| Consulta expedientes | https://alhendin.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| PGOU (web) | https://alhendin.es/pgou/ | Enlace a SITUA Junta de Andalucía |
| PGOU PDF | https://alhendin.es/wp-content/uploads/2016/05/Normas-Urbanisticas-ADefinitiva.pdf | Normas urbanísticas aprobación definitiva |
| Impresos urbanismo | https://alhendin.es/impresos-urbanismo/ | Formularios licencias obra/actividad |
| Licencias obra | https://alhendin.es/impresos-urbanismo/licencias-de-obra-mayor-y-menor/ | PDFs solicitud, DR, tasas |
| Licencias actividad | https://alhendin.es/impresos-urbanismo/licencias-de-actividad/ | Apertura, cambio titularidad |
| Tablón web (legacy) | https://alhendin.es/tablon-de-anuncios/ | Imágenes escaneadas del tablón físico (2014–2020) |
| SITUA | http://ws041.juntadeandalucia.es/medioambiente/situadifusion/pages/search.jsf | Visor planeamiento Junta Andalucía |
| Diputación Granada | https://www.dipgra.es/municipios/asistencia-a-municipios/asistencia/asistencia-urbanistica/planeamiento-urbanistico/ | Asistencia planeamiento provincial |
| Incidencias urbanas | https://aytoalhendin-publicform.incidenciasurbanas.com/ | Formulario incidencias (no expedientes) |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Alcaucín, Tomares, Cártama.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}` (PDF en visor sede).
- **Paginación:** ~10 filas visibles; botón «Mostrar más» vía Wicket AJAX (adapter parsea primera página).

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Expediente | Procedimiento | Descripción |
|-------|------------|---------------|-------------|
| 28/08/2026 | 3608/2021 | Planeamiento General | Aprobación definitiva innovación-modificación PGOU Alhendín |
| 27/08/2026 | 2393/2023 | Planeamiento de Desarrollo | Proyecto de actuación para la construcción |

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites informativos en web municipal (`/impresos-urbanismo/`) y sede (`/dossier`).
- Modelos: solicitud licencia obras, declaración responsable obra mayor/menor, primera ocupación, segregación.
- Las licencias concedidas publicadas aparecen en el tablón como edictos (cuando existan).

## Proyectos / planeamiento

- **Tablón:** certificados de acuerdo pleno sobre planeamiento (PGOU, actuaciones).
- **Web municipal:** PGOU PDF (normas urbanísticas 2016), página PGOU con enlace SITUA.
- **WP REST:** posts filtrados por `planeamiento`, `pgou`, `urbanismo`, `innovacion`.
- **Junta Andalucía:** innovaciones PGOU publicadas en BOJA (p. ej. sectores SUB-07, API S-10).
- **Diputación Granada:** asistencia técnica en planeamiento (sin ficha individual tipo Dip. Málaga).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA / SituaDIFusión (Junta de Andalucía): planeamiento aprobado por municipio; sin campo de enlace a expediente del tablón.
  - VITUA (IECA): visor cartográfico autonómico; sin query por código expediente municipal.
  - Diputación Granada: documentación de asistencia en planeamiento, sin WFS/ArcGIS por expediente.
  - Tablón espublico: PDFs de acuerdos plenario sin georreferencia embebida.
- **Estrategia:** los visores regionales muestran zonificación PGOU agregada, **sin enlace a expediente** del tablón. Los anuncios son PDF sin coords.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST accesible por código de expediente.
  - Consulta expedientes en sede requiere login.
  - Tablón paginado con AJAX Wicket (solo primera página en adapter).
  - El orquestador aplicará centroide municipio (37.1586, -3.6572) + jitter.

## Limitaciones generales

- Sin listado histórico público de licencias concedidas (solo trámites informativos + tablón).
- Tablón web municipal legacy con imágenes JPG escaneadas (no parseadas).
- `/dossier` puede ser lento (>50 s) en CI.
- SITUA usa host legacy `ws041.juntadeandalucia.es` enlazado desde web municipal.

## Adapter implementado

- `municipio/adapters/alhendin.py` — WordPress REST + tablón espublico + seeds PGOU/SITUA/Diputación.
