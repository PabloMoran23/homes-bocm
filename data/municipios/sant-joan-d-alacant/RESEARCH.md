# Sant Joan d'Alacant — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `sant-joan-d-alacant` |
| INE | 03119 (provincia Alicante) |
| Boletín | DOGV (`dogv`) |
| CMS web | WordPress + Elementor (PowerPack) |
| Sede | espublico gestiona (`santjoandalacant.sedelectronica.es`) |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web oficial | https://www.santjoandalacant.es | WordPress; bloquea algunos bots (403 sin UA) |
| Área Urbanismo | https://www.santjoandalacant.es/area-urbanismo/ | Sección planeamiento (page id 85149) |
| PGOU 2013 | https://www.santjoandalacant.es/area-urbanismo/pgou-2013/ | Plan general + 7 modificaciones puntuales |
| Sede electrónica | https://santjoandalacant.sedelectronica.es/info | espublico gestiona (requiere cookies) |
| Tablón | https://santjoandalacant.sedelectronica.es/board | Anuncios/edictos HTML tabla Wicket |
| Trámites | https://santjoandalacant.sedelectronica.es/dossier | Catálogo ~126 trámites (licencias ART. 19–49) |
| Transparencia | https://santjoandalacant.sedelectronica.es/transparency | Carpetas AJAX (no scrapeable sin sesión) |
| WP REST API | https://www.santjoandalacant.es/wp-json/wp/v2/ | Posts `areas=505` (275 noticias Urbanismo) |

### Modificaciones PGOU publicadas (páginas WP)

- Modificación Nº 1–8 del PGOU 2013 (PDFs memoria, BOP, documentación técnica)
- Programa de Paisaje Avda. Miguel Hernández y CN 332
- Registro de Programas / Agrupaciones de Interés Urbanístico

## Cómo se listan expedientes

### WordPress (proyectos / planeamiento)

- **Páginas** bajo `/area-urbanismo/` con PDFs en listas Elementor (`elementor-icon-list`).
- **Noticias** taxonomía custom `areas` id **505** («Urbanismo», 275 entradas).
- Acceso vía REST: `/wp-json/wp/v2/pages?parent=85149` y `/posts?areas=505`.

### Sede espublico (licencias / edictos)

- **Tablón** `/board`: tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom` y enlaces `preview-document/{uuid}`.
- **Catálogo** `/dossier`: enlaces `catalog/t/{uuid}` a formularios de trámites (licencias de obra, DR, comunicaciones previas).
- Consulta de expedientes (`/expedientes`) requiere identificación; no hay listado público.

### Limitaciones

- Web principal devuelve 403 a curl sin User-Agent; REST API funciona con UA identificable.
- Tablón muestra ~10 anuncios recientes (paginación Wicket/AJAX); pocos edictos urbanísticos activos.
- Transparencia sede carga subcarpetas vía AJAX (no determinista sin sesión).
- No hay dataset JSON/API de licencias concedidas históricas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - ICV `terramapas.icv.gva.es/0702_Planeamiento` WFS `InventarioSuSuz` con `cod_ine_mun=03119` → **0 polígonos** para Sant Joan d'Alacant.
  - Generalitat Valenciana: documentación PGOU en `mediambient.gva.es/auto/urbanismo/.../03119 SANT JOAN D'ALACANT/` (PDFs/planos, sin API GeoJSON).
  - No visor ArcGIS/WFS municipal público enlazado desde el portal.
- **Estrategia:** sin geometría en adapter; orquestador aplicará centroide municipio + jitter.
- **Limitaciones:** expedientes en tablón/PDF sin georreferencia; ICV sin sectores SUZ/UA para este municipio en el inventario consultado.

## Adapter implementado

- `municipio/adapters/sant_joan_d_alacant.py` — `SantJoanDAlacantAyuntamientoAdapter`
- Fuentes: WP REST (páginas PGOU + noticias Urbanismo) + sede tablón + catálogo trámites.
