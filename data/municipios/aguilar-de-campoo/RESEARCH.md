# Aguilar de Campoo — investigación portal ayuntamiento

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal | https://aguilardecampoo.es |
| Urbanismo (archivo WP) | https://aguilardecampoo.es/urbanismo/ |
| Planeamiento revisado (PGOU/PEPCH) | https://aguilardecampoo.es/urbanismo/planeamiento-general-revisado/ |
| Sede electrónica (espublico gestiona) | https://aguilardecampoo.sedelectronica.es |
| Tablón de anuncios | https://aguilardecampoo.sedelectronica.es/board/ |
| Catálogo de trámites | https://aguilardecampoo.sedelectronica.es/dossier |
| Documentación oficial (modelos licencias) | https://aguilardecampoo.es/ayuntamiento/documentacion-oficial/ |
| PLAI JCYL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=34&municipio=4 |
| PLAI JCYL (archivo aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=34&municipio=4 |

**Nota:** `www.aguilardelcampoo.es` devuelve HTTP 500; el dominio activo es `aguilardecampoo.es`.

## CMS / sede

- **Web:** WordPress (plantilla Diputación de Palencia / Divi). REST API deshabilitada (`rest_cannot_access`).
- **Sede:** espublico gestiona (Wicket). Tablón con `preview-document/{uuid}`; categorías «Licencias Urbanísticas» y «Planeamiento de Desarrollo».
- **Licencias:** no hay dataset abierto de concesiones; el tablón publica anuncios puntuales y la sede expone trámites informativos. Modelos en «Documentación oficial» (sección Urbanismo, Obras Públicas y Medio Ambiente).

## Proyectos / expedientes

1. **Archivo urbanismo WP** — posts en `/urbanismo/` (paginación hasta ~4 páginas): estudios de detalle, PGOU, PEPCH, PERI, modificaciones puntuales.
2. **Tablón sede** — anuncios de información pública y aprobaciones iniciales (p. ej. estudio de detalle AA-03, expediente 2358/2025).
3. **PLAI JCYL** — instrumentos de planeamiento del municipio (código PLAI `provincia=34`, `municipio=4`).
4. **SIUCyL WFS** — sectores e instrumentos aprobados con geometría.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito`
  - Filtro: `n_mun = 'Aguilar de Campoo'` (12 sectores/ámbitos en WFS)
  - Campos útiles: `n_num_sect`, `n_sector`, `c_id_sect`, geometría GeoJSON EPSG:4326
- **Estrategia:** descarga masiva WFS por municipio; enriquecimiento por código de sector (`SUR-01`, `SU-NC 03`, `AA-03`, etc.) extraído del título del anuncio/tablon.
- **Limitaciones:**
  - No hay visor municipal ArcGIS enlazado a expedientes individuales.
  - Licencias del tablón no traen polígono; solo proyectos con código de sector emparejable en WFS.
  - REST WP cerrada; fechas de posts no siempre en HTML del listado.

## Limitaciones generales

- Sin API JSON en la web municipal.
- Catálogo `/dossier` puede responder lento (>45 s); el adapter prioriza tablón + archivo WP.
- Licencias: solo anuncios publicados + páginas informativas de trámites (sin listado histórico de concesiones).
