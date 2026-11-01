# Calvià — investigación portal ayuntamiento

Municipio: **Calvià** (`calvia`), Illes Balears. Web oficial: [calvia.com](https://www.calvia.com) (Plone, multilingüe).

## Fuentes

| Área | URL | Formato |
|------|-----|---------|
| Urbanismo (índice) | https://www.calvia.com/es/areas-municipales/urbanismo | Plone carpetas + RSS |
| Planeamiento en tramitación | https://www.calvia.com/es/areas-municipales/urbanismo/planeamiento-en-tramitacion/rss.xml | RSS → PDFs / documentos |
| PGOU revisión | https://www.calvia.com/es/areas-municipales/urbanismo/pgou-revision/rss.xml | RSS → subcarpetas y PDFs |
| Planeamiento vigente | https://www.calvia.com/es/areas-municipales/urbanismo/planeamiento-vigente/rss.xml | RSS |
| Trámites / modelos licencia | https://www.calvia.com/es/areas-municipales/urbanismo/urbanismo | HTML enlaces a PDFs y catálogo 2021+ |
| Anuncios / IP | https://www.calvia.com/es/ayuntamiento/normativa-y-anuncios/anuncios | Carpetas (información pública vacía en RSS) |
| Sede electrónica | https://www.calvia.com/es/tramites/sede-electronica | Página informativa (carga lenta); sin tablón público scrapeable |
| Visor obras mayores | https://www.calvia.com/es/areas-municipales/urbanismo/visor-obras-mayores | Plone (timeout frecuente en cloud) |

## Listado expedientes / planeamiento

- **Proyectos**: feeds RSS de Plone bajo `urbanismo/` (principalmente `planeamiento-en-tramitacion` y `pgou-revision`). Cada `<item>` aporta título, `pubDate` y `guid` (URL de documento o carpeta).
- **Licencias**: no hay tablón CSV/HTML de concesiones. El ayuntamiento publica **modelos y guías** en `urbanismo/urbanismo`. Los expedientes de obra georreferenciados están en **IDELMA WFS** (`M011_EXP_OBRA`).

## Licencias

- Trámites informativos en web (licencia urbanística, CPO/DEC, primera ocupación).
- Dataset operativo: **WFS** `M011_Calvia:M011_EXP_OBRA` en `ide.idelma.cat` (~19 791 puntos, campos `expte`, `refecada`, geometría punto EPSG:4326).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS obras: `https://ide.idelma.cat/geoserver/M011_Calvia/wfs` → `M011_EXP_OBRA` (Point, join por expediente).
  - WFS sectores: `M011_SECTORS_URBANISTICS` (MultiPolygon, campo `urbanitz`; join textual débil con títulos RSS).
  - SITMUN PGOU vigente: https://sitmun.idelma.cat/calvia_vigent (enlace desde visor web).
  - SITMUN PGOU tramitación: https://sitmun.idelma.cat/urb_calvia
  - Visor PGOU web: https://www.calvia.com/es/areas-municipales/urbanismo/visores-informacion-geografica/visor-pgou-vigente
- **Estrategia:** licencias con polígono/punto desde WFS obras; proyectos RSS enriquecidos si el título contiene el nombre de sector (`urbanitz`) presente en `M011_SECTORS_URBANISTICS`.
- **Limitaciones:** visor obras mayores y sede con timeouts; SITMUN sin API JSON pública ligera al expediente; listados RSS son PDFs sin geometría embebida; información pública (anuncios) sin ítems RSS activos.

## Limitaciones generales

- Sin boletín autonómico asociado en cola (`bocm_count: 0`).
- Sede electrónica no expone listado masivo de licencias concedidas (solo trámites / WFS).
- Paginación WFS necesaria (miles de expedientes de obra).
