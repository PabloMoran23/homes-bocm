# Majadahonda — investigación portal ayuntamiento

## Sitio oficial

- **Web principal:** https://www.majadahonda.org (Liferay Portal)
- **Sede electrónica:** https://sede.majadahonda.org
- **Tablón virtual sede:** `https://sede.majadahonda.org/portal/tablonVirtual.do?subseccion=TABLONVIRTUAL&opc_id=175&pes_cod=4&ent_id=2&idioma=1` (contenido cargado por JS; sin filas HTML estáticas)
- **Transparencia:** https://transparencia.majadahonda.org

## Urbanismo — URLs semilla

| Sección | URL | Formato |
|---------|-----|---------|
| Urbanismo (índice) | https://www.majadahonda.org/es/urbanismo-obras-y-licencias | Liferay menú |
| Anuncios IP urbanísticos | https://www.majadahonda.org/informacion-publica-anuncios-urbanisticos | Asset Publisher: tabla con título, fecha publicación, plazo |
| Anuncios urbanísticos | https://www.majadahonda.org/anuncios-urbanisticos | Mismo listado (duplicado) |
| Planeamiento | https://www.majadahonda.org/planeamiento-urban%C3%ADstico | Enlaces a planes parciales/especiales/estudios |
| Planes parciales | https://www.majadahonda.org/planes-parciales | HTML + PDF `/documents/...` |
| Planes especiales | https://www.majadahonda.org/planes-especiales | HTML |
| Estudios de detalle | https://www.majadahonda.org/estudios-de-detalle | HTML |
| Trámites licencias | https://www.majadahonda.org/urbanismo-tramites-y-servicios | Tabla THU + enlaces impresos |
| Impresos licencia/DR | https://www.majadahonda.org/urbanismo-impresos | Asset Publisher por trámite |
| SIT Madrid | https://www.majadahonda.org/sit-madrid | Enlace al visor autonómico |

## Formato y acceso

| Fuente | Formato | Acceso |
|--------|---------|--------|
| Anuncios IP | Liferay Asset Publisher (`class="title"` + fechas DD/MM/YY) | Público, scrapeable |
| Detalle anuncio | `/informacion-publica-anuncios-urbanisticos/-/asset_publisher/.../content/<slug>` | Texto decreto/resolución; PDFs poco frecuentes |
| Planeamiento | PDFs en `/documents/<site>/<folder>/<file>.pdf/<uuid>` | Público |
| Licencias | Páginas informativas de impresos (no listado de concesiones) | Público |
| Tablón sede | JS/AJAX | No scrapeable sin navegador |

## Licencias

- No hay dataset público de concesiones con coordenadas.
- Tramitación vía sede electrónica (certificado). El portal publica **impresos normalizados** (licencia obras, DR, actividades, parcelación).
- El adapter devuelve páginas informativas de trámites (paridad mínima `tipo` + `url`).

## Proyectos / expedientes

- **18 anuncios** vigentes en información pública (planes parciales/especiales, modificaciones PGOU, estudios de detalle, PEM).
- Cada fila enlaza a ficha Liferay con texto del acuerdo/decreto y fechas de exposición.
- Documentos históricos de planeamiento en secciones PGOU/planes parciales (PDF compendio R21592-21691).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor SIT Comunidad de Madrid: `http://idem.madrid.org/cartografia/sitcm/html/visor.htm?municipio=080`
  - WFS ámbitos planeamiento: `https://idem.comunidad.madrid/geoserver3/ows` — capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='MAJADAHONDA'` (~40 polígonos APR-*)
- **Estrategia:** Tras obtener metadatos del proyecto, emparejar título con `DS_NOMB_AMB` (p. ej. «Arroyo del Arcipreste» → `APR-21 ARROYO DEL ARCIPRESTE`) y descargar polígono WFS en EPSG:4326.
- **Limitaciones:**
  - SIT cubre **ámbitos de planeamiento aprobado**, no expedientes puntuales ni licencias de obra.
  - Planes especiales nuevos (p. ej. «El Carralero II») pueden no tener ámbito en WFS.
  - Tablón sede y licencias sin georreferencia.
  - No hay visor municipal ArcGIS propio.

## Estrategia adapter

1. Scrape listados Asset Publisher (`informacion-publica-anuncios-urbanisticos`, `anuncios-urbanisticos`).
2. Enriquecer con fecha del detalle y PDF si existe.
3. Añadir PDFs de secciones planeamiento.
4. Licencias: impresos de `urbanismo-impresos`.
5. Geometría: query WFS SIT por nombre de ámbito extraído del título.
