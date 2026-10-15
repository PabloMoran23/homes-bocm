# San Agustín de Guadalix — investigación portal ayuntamiento

**Municipio:** San Agustín de Guadalix (slug BOCM; nombre oficial IGN/portal: San Agustín del Guadalix)  
**Fecha:** 2026-10-15  
**BOCM regional (referencia):** 1 aviso (variante ortográfica «de»; el mismo término municipal figura como «del» en 32 avisos, slug `san-agustin-del-guadalix`)

## Nota sobre el nombre

El directorio de administraciones (PAG) registra la oficina como «Ayuntamiento de San Agustín **de** Guadalix» (`aytosag@aytosag.es`), mientras el portal municipal usa el nombre «San Agustín **del** Guadalix». Es un único municipio (INE 28131, CP 28750). No existe portal distinto para la variante «de».

## Resumen

El ayuntamiento publica planeamiento y documentación urbanística en el **portal de transparencia** (WordPress Divi en `sanagustindelguadalix.net`). La **sede electrónica** (`sanagustindelguadalix.sedelectronica.es`, espublico gestiona) expone tablón de anuncios y catálogo de trámites. No hay visor urbanístico ni listado público de licencias concedidas con coordenadas.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Portal transparencia — urbanismo | `https://sanagustindelguadalix.net/portal-transparencia/normativa-urbanismo/` | WordPress REST + PDFs | Proyectos (PGOU, PERI, convenios) |
| Formularios urbanismo | `https://sanagustindelguadalix.net/formularios-solicitudes/#urbanismo` | HTML + PDFs trámite | Licencias informativas |
| Sede — tablón | `https://sanagustindelguadalix.sedelectronica.es/board/` | HTML tabular (espublico) | Edictos urbanismo/licencias |
| Sede — trámites | `https://sanagustindelguadalix.sedelectronica.es/dossier` | Catálogo HTML | Trámites informativos |

Investigación detallada y patrones de scrape: ver `data/municipios/san-agustin-del-guadalix/RESEARCH.md` (mismas URLs y limitaciones).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:** plugin Leaflet (`wp-mapit`) sin API REST; PDFs de planos sin georref; sede sin GIS/WFS
- **Estrategia:** centroide municipio + jitter vía orquestador `geocode`
- **Limitaciones:** sin ArcGIS/WFS/GeoJSON municipal enlazable a expedientes

## Estrategia de ingesta

- **Adapter:** `SanAgustinDeGuadalixAyuntamientoAdapter` (delega en lógica `san_agustin_del_guadalix` con `id_prefix` `san-agustin-de-guadalix`)
- **IDs:** `san-agustin-de-guadalix-{lic|proy}-{sha256[:14]}`
- **source:** `ayuntamiento`

## Paridad esperada

- `proyectos`: ok (~280+ PDFs/páginas urbanismo + tablón)
- `licencias`: partial (formularios y trámites; sin concesiones georreferenciadas)
- `with_geometry`: 0
