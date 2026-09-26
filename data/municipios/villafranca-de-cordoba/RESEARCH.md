# Villafranca de Córdoba — investigación portal ayuntamiento

**Municipio:** Villafranca de Córdoba (Córdoba, Andalucía)  
**Slug:** `villafranca-de-cordoba`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://villafrancadecordoba.es | **Operativa** — WordPress Divi |
| Urbanismo / PGOU | https://villafrancadecordoba.es/ayuntamiento-planeamiento_urbano_pgou/ | **Operativa** — 29 PDFs normativa (PGOU, Normas Subsidiarias 2016) |
| Portal PGOM-POU | https://planurbanismo.villafrancadecordoba.es/ | **Operativa** — WordPress Blocksy; elaboración PGOM-POU (LISTA) |
| Documentos PGOM | https://planurbanismo.villafrancadecordoba.es/documentos/ | Página informativa (sin PDFs directos en HTML) |
| Sede electrónica | https://sede.eprinsa.es/vfranca | **Operativa** — plataforma eprinsa (Diputación de Córdoba), Ember.js SPA |
| Tablón de edictos | https://sede.eprinsa.es/vfranca/tablon-de-edictos | **SPA** — componente `wec-bulletins`; requiere token de sesión |
| Transparencia | https://transparencia.villafrancadecordoba.es | Portal separado |
| Catastro | https://villafrancadecordoba.es/catastro/ | Información catastral (sin visor SIG) |

## Cómo se listan expedientes / proyectos

- **WordPress REST API** (`/wp-json/wp/v2/posts`):
  - Categoría `urbanismo` (id 45): reparcelación sector PPI-6, aprobaciones iniciales/definitivas.
  - Búsquedas: `sector`, `edicto`, `reparcelacion`, `urbanizacion`, `pgom` — anuncios de urbanización Sector PP-I-6 (2025), avances PGOM (2025).
- **Página urbanismo:** PDFs estáticos de instrumentos vigentes (memoria, ordenación estructural, calificación del suelo, infraestructuras).
- **Portal PGOM-POU:** noticias de participación ciudadana y avance del nuevo plan; sin expedientes numerados.
- **Tablón eprinsa:** edictos de información pública y licencias (cuando se publican); no accesible vía API REST sin sesión.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Las licencias publicadas como edictos deberían aparecer en el tablón eprinsa.
- Trámites vía sede (`/tramites`) y consulta de expedientes con autenticación (`/expedientes`).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - VITUA (Junta de Andalucía): https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ — cartografía LISTA/PGOU por municipio; sin campo expediente del ayuntamiento.
  - SITUA: documentación de instrumentos de planeamiento autonómicos; sin query por código de expediente municipal.
  - PGOU web: PDFs de planos (calificación del suelo, ordenación) sin servicio WFS/ArcGIS enlazado.
  - Mapa municipal en home: imagen estática, no visor interactivo.
- **Estrategia:** VITUA muestra clasificación del PGOU vigente, pero **no enlaza** con filas del tablón ni expedientes municipales. Los anuncios son PDF/texto sin georreferencia embebida.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST accesible por expediente o sector desde el portal municipal.
  - Tablón SPA sin API pública.
  - El orquestador aplicará centroide municipio + jitter (`centroid: [37.9633, -4.5469]`).

## Limitaciones generales

- Tablón eprinsa no scrapeable determinísticamente (token de sesión en `apis.dipucordoba.es`).
- Portal PGOM-POU sin documentos descargables en HTML público.
- Consulta de expedientes requiere login Cl@ve/certificado.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.villafranca_de_cordoba:VillafrancaDeCordobaAyuntamientoAdapter`
- Fuentes: WP categoría urbanismo + búsquedas sector/edicto/reparcelación + PDFs página urbanismo + noticias planurbanismo + páginas informativas sede eprinsa (licencias).
