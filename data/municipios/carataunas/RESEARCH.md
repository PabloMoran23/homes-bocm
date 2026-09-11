# Carataunas — investigación portal ayuntamiento

**Municipio:** Carataunas (Granada, Andalucía)  
**Slug:** `carataunas`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 18043

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web municipal | https://www.carataunas.es | **Operativa** — CMS SAGA Alhambra (Diputación Granada) |
| Plan de ordenación urbana | https://carataunas.es/ayuntamiento/plan-de-ordenacion-urbana/ | GaleríaDescargas con PDF índice PGOU |
| Tablón web | https://carataunas.es/ayuntamiento/tablon-de-anuncios-00001 | Timeout en CI; sede es alternativa |
| Sede electrónica | https://carataunas.sedelectronica.es | **Operativa** — espublico gestiona (`insecure_ssl`) |
| Tablón de anuncios | https://carataunas.sedelectronica.es/board/ | Tabla HTML ~4 filas recientes |
| Transparencia urbanismo | https://carataunas.sedelectronica.es/transparency/1b67b490-e8f9-43f4-a647-84ff1ae9e025/ | Sección 7 URBANISMO (53 docs en 7.1 Planeamiento; expansión AJAX) |
| Catálogo trámites | https://carataunas.sedelectronica.es/dossier | Timeout frecuente en CI |
| Consulta expedientes | https://carataunas.sedelectronica.es/expedientes | Requiere autenticación |
| BOJA PGOU 2025 | https://www.juntadeandalucia.es/boja/2025/212/52 | Aprobación definitiva PGOU |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Consulta planeamiento autonómico |
| BOP Diputación Granada | https://bop.dipgra.es | Anuncios municipales (SAGA) |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), patrón Andalucía (Alcaucín, Cómpeta, Almuñécar).
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** solo primera página visible en HTML estático.
- **Categorías urbanísticas observadas:** «Plan Local de Instalaciones y Equipamientos Deportivos» (exp. 62/2023).

## Licencias de obra

- No hay dataset público histórico de concesiones con coordenadas.
- Trámites vía sede (`/dossier`, `/expedientes` con login).
- Edictos de licencias/actividad publicados en tablón cuando procede.
- El adapter incluye páginas informativas (tablón, catálogo sede, trámites web).

## Proyectos / planeamiento

- **PGOU:** aprobación definitiva publicada en BOJA (noviembre 2025); documentación en transparencia sede (7.1 Planeamiento urbanístico, 53 documentos) y galería web (índice PDF 2022).
- **Web SAGA:** página POU con GaleriaDescargas; enlace a transparencia sede.
- **Tablón sede:** anuncios BOP (Plan Local deportivo, modificaciones presupuestarias filtradas).
- **SITUA:** consulta del PGOU vigente en Junta de Andalucía (sin query por código de expediente del tablón).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - SITUA/VITUA (`ws132.juntadeandalucia.es/situadifusion`): visor regional del PGOU; sin enlace por código de expediente del tablón municipal.
  - Transparencia sede: PDFs con planos; expansión de carpetas vía Wicket AJAX (no listado estático).
  - Web municipal: GaleriaDescargas con PDF índice; sin API GeoJSON/WFS.
  - No hay visor urbanístico municipal propio (ArcGIS/WFS).
- **Estrategia:** no hay fuente GIS pública enlazable por expediente; el orquestador usará centroide municipio + jitter.
- **Limitaciones:** documentos son PDF; tablón paginado; transparencia requiere JS; consulta expedientes requiere login.

## Limitaciones generales

- Web tablón (`tablon-de-anuncios-00001`) con timeout en entornos automatizados; se usa tablón sede.
- Sede con certificado que requiere `insecure_ssl: true` en CI.
- Transparencia: 53 documentos de planeamiento tras expandir 7.1 (no scrapeables sin sesión AJAX).
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.carataunas:CarataunasAyuntamientoAdapter`
- Fuentes: tablón sede + página POU (PDFs) + transparencia (enlace) + BOJA PGOU + SITUA.
