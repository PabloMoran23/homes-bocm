# Bonares — investigación portal ayuntamiento

**Municipio:** Bonares (Huelva, Andalucía)  
**Slug:** `bonares`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://bonares.es | **Inaccesible** — HTTPS sin respuesta desde CI; HTTP redirige sin contenido |
| Urbanismo (web) | https://bonares.es/es/servicios/urbanismo/ | Documentada; no verificable en CI |
| Sede electrónica | https://bonares.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://bonares.sedelectronica.es/board/ | **Operativa** — tabla HTML (~10 filas) |
| Transparencia | https://bonares.sedelectronica.es/transparency | **Operativa** — categorías + documentos recientes |
| Catálogo trámites | https://bonares.sedelectronica.es/dossier | Redirige a `/dossier.0`; bucle de redirección en CI |
| Consulta expedientes | https://bonares.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Visor regional planeamiento (sin API REST por expediente) |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta, Lepe, Enguera.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página.

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Expediente | Descripción |
|-------|------------|-------------|
| 29/06/2026 | 396/2026 | Aprobación definitiva Plan Municipal contra el Cambio Climático de Bonares |
| 14/01/2013 | — | Resolución alcaldía — declaración de ruina (transparencia) |

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites vía sede (`/dossier`, `/expedientes` con login).
- Web municipal documenta sección urbanismo (inaccesible en CI).
- Las licencias concedidas aparecerían en el tablón como edictos (ninguna en la página actual).

## Proyectos / planeamiento

- **Tablón:** Plan Municipal contra el Cambio Climático (disposición normativa).
- **Transparencia:** declaración de ruina (Cuarteladas, 2013) en categoría urbanismo.
- **SITUA:** consulta regional de instrumentos de planeamiento (PGOU/PGOM si existiera); sin descarga GeoJSON por código de expediente del ayuntamiento.
- Sin visor urbanístico municipal propio ni datos abiertos georreferenciados.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA/VITUA (Junta de Andalucía): planeamiento regional embebido; iframe JSF sin WFS/REST accesible por expediente del tablón.
  - Diputación de Huelva: sin geoportal urbanístico enlazado desde la sede de Bonares.
  - Tablón/transparencia: PDFs sin georreferencia embebida.
- **Estrategia:** no hay MapServer/WFS/GeoJSON consultable por código de expediente; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Sin visor ArcGIS municipal.
  - Web bonares.es inaccesible desde CI.
  - Categorías de transparencia cargadas vía Wicket AJAX (solo documentos visibles en página raíz).

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página).
- `/dossier` con bucle de redirección en entorno agente.
- `/info` timeout en CI.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.bonares:BonaresAyuntamientoAdapter`
- Fuentes: tablón sede + transparencia (preview-document) + enlace SITUA + páginas informativas trámites.
- IDs: `bonares-lic-*` / `bonares-proy-*` (sha256[:14]).
