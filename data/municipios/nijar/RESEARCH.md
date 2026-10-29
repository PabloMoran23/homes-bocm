# Níjar — investigación portal ayuntamiento

**Municipio:** Níjar (Almería, Andalucía)  
**Slug:** `nijar`  
**Boletín:** sin boletín regional asociado en cola (`bocm_count: 0`)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://nijar.es | **Operativa** — WordPress (Salient/Nectar) |
| Área urbanismo | https://nijar.es/ayuntamiento/areas/urbanismo-e-infraestructuras/ | **Operativa** — enlaces institucionales |
| Noticias urbanismo | https://nijar.es/noticias/categoria/urbanismo/ | **Operativa** — ~20 entradas/página, paginación |
| Sede electrónica | https://nijar.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://nijar.sedelectronica.es/board/ | **Operativa** — ~10 anuncios vigentes |
| Transparencia sede | https://nijar.sedelectronica.es/transparency | **Parcial** — carpeta «7. INFORMACIÓN MEDIOAMBIENTAL Y URBANÍSTICA» (168 docs), árbol AJAX |
| Catálogo trámites | https://nijar.sedelectronica.es/dossier | **Operativa** — licencias vía sede |
| WFS sectores (Dip. Almería) | https://app.dipalme.org/geoserver/urbanismo/wfs | **Operativa** — `urbanismo:v_siu_ambitos_o_sectores`, `cod_ine=04066` |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket), mismo patrón que Vera, Cómpeta, San Javier.
- **Columnas:** `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** `preview-document/{uuid}`.
- **Ejemplos urbanísticos (oct 2026):** edicto investigación titularidad camino (POL 237/241); edicto licencia apertura restaurante.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Edictos de licencia en tablón (apertura actividad, obra).
- Trámites en sede `/dossier`; consulta expedientes con autenticación.
- Adapter incluye páginas informativas (tablón, trámites, área urbanismo web).

## Proyectos / planeamiento

- **Tablón:** edictos urbanísticos y licencias con texto de expediente.
- **Noticias WP:** obras públicas, plan especial puerto seco, saneamiento, alumbrado, rehabilitación (categoría urbanismo).
- **REST WP:** `/wp-json/wp/v2/*` devuelve 403 («No tienes autorización»); scrape HTML de listados y artículos.
- **Transparencia:** documentación urbanística en carpeta sede (168 ítems) sin API pública; no scrapeado por login/ AJAX.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Diputación Provincial de Almería: `urbanismo:v_siu_ambitos_o_sectores`, filtro `cod_ine='04066'`, GeoJSON EPSG:4326, campo `sector`.
  - No hay visor municipal ArcGIS enlazado a código de expediente del tablón.
  - SITUA/Junta: planeamiento regional; sin query fiable por expediente municipal del tablón.
- **Estrategia:** emparejar título del proyecto/noticia con nombre de sector en WFS; rellenar `geom_geojson` cuando hay coincidencia.
- **Limitaciones:** títulos sin código de sector no obtienen polígono; parcelas/caminos (POL/PARC) sin capa WFS municipal.

## Limitaciones generales

- Tablón con mezcla de anuncios no urbanísticos (personal, pleno).
- WP REST bloqueado para agentes no autenticados.
- Sin histórico masivo de licencias concedidas en abierto.

## Adapter implementado

- `municipio.adapters.nijar:NijarAyuntamientoAdapter`
- Fuentes: tablón sede + noticias urbanismo (HTML) + WFS Dipalme (geometría parcial).
