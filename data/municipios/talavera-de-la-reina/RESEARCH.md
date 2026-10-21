# Talavera de la Reina — investigación portal urbanismo

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://talavera.es |
| Área urbanismo (WP multisite) | https://urbanismo.talavera.es |
| Expedientes en información pública (planeamiento) | https://urbanismo.talavera.es/tramites-en-informacion-publica/planeamiento-y-gestion/ |
| Planeamiento / POM (WPFD, ~100 PDFs) | https://urbanismo.talavera.es/planeamiento/ |
| Impresos y solicitudes (licencias) | https://urbanismo.talavera.es/impresos-documentacion-y-solicitudes/ |
| Sede electrónica (SIAL ADMÓNDIGITAL) | https://sede.talavera.org (`entidad=45165`) |
| Tablón de edictos | https://sede.talavera.org/web/tablonEdictos.do?opcion=0&entidad=45165&idioma=1 |
| Visores cartográficos | https://urbanismo.talavera.es/visor/ |

## Listado de expedientes / proyectos

- **WP File Download (Elementor):** las páginas de trámites en información pública y `planeamiento/` enlazan PDFs bajo `/download/{cat}/{slug}/{id}/{nombre}.pdf`. Los anuncios recientes incluyen PERIM, estudios de detalle y convenios urbanísticos (códigos tipo `00632/2025/URB`, `exp-804-2026-urb`).
- **Tablón sede:** el listado se obtiene con `POST` a `/web/tablonEdictos.do` (`opcion=5`, filtros opcionales). La respuesta embebe arrays `listaJS[j]` con título, fecha, departamento y enlace BOP Diputación Toledo cuando aplica.
- **DOCM:** algunos anuncios se republican en el Diario Oficial de Castilla-La Mancha (referencia cruzada en PDFs).

## Licencias

- No hay dataset público de concesiones con coordenadas.
- **Formularios** descargables (obra mayor/menor, comunicación previa, DR, parcelación) en `impresos-documentacion-y-solicitudes` → `talavera.es/download/.../licencias-y-actos-comunicados/`.
- **Catálogo sede:** búsqueda `licencia obra` en `catalogoAsuntos.do` (tramitación electrónica).
- **Tablón:** edictos puntuales de licencias/actividad cuando se publican (filtro por texto).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Página visor: planos PDF del POM (calificación, sistemas generales) y enlaces a visores temáticos JCCM (`castillalamancha.maps.arcgis.com` — galería genérica, sin capa REST enlazada a expediente municipal).
  - SITCM Comunidad de Madrid: municipio no presente (Talavera es CLM).
  - Expedientes WPFD / tablón: solo PDF sin servicio WMS/WFS por código de expediente.
- **Estrategia:** el orquestador usará centroide municipal (`manifest.portal.config.centroid`) + jitter.
- **Limitaciones:** sin API GIS municipal; ArcGIS JCCM no consultable por `expediente` desde el adapter.

## Limitaciones técnicas

- Sede responde en `ISO-8859-15`; tablón requiere POST (iframe `opcion=5`).
- `planeamiento/` mezcla documentación histórica del POM con expedientes recientes; el adapter filtra por regex urbanística.
- Sin boletín BOCM asociado en cola (`bocm_count: 0`).
