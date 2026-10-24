# Torrelavega — investigación portal ayuntamiento

## Fuentes

| Recurso | URL | Uso |
|---------|-----|-----|
| Web municipal | https://torrelavega.es | WordPress (Yoast); sección urbanismo |
| Urbanismo | https://torrelavega.es/servicios-al-ciudadano/urbanismo/ | Enlaces a PGOU, sede STA (tablón, catálogo) |
| PGOU (microsite) | https://www.pgou-torrelavega.es/ | Vertary CMS: `/noticias`, `/documentos`, PDFs revisión PGOU |
| Sede electrónica | https://sede.torrelavega.es/ | STA T-Systems |
| Catálogo trámites | `.../PAGE_CODE=CATALOGO` | `dataset_CATSERV` embebido (87 trámites; ~29 URB_*) |
| Tablón anuncios | `.../PAGE_CODE=PTS2_TABLON` | Sin `dataset_PTS2_TABLON` en HTML inicial (carga cliente/AJAX) |
| Tablón ayuntamiento | `.../PAGE_CODE=PTS2_TABLON_AYUNTAMIENTO` | Igual: sin dataset inline |
| Tablón WP | https://torrelavega.es/ayuntamiento/tablon-electronico-ayuntamiento-de-torrelavega/ | Secciones temáticas; sin listado urbanístico scrapeable |
| SIUCAN WFS | https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer | Capa `Urbanismo:Sectores`, INE **39087** |
| AUCAN Cantabria | https://aplicacionesweb.cantabria.es/aucan/public/zona/costacentral/torrelavega | Timeout en entorno cloud (>60s) |

## Proyectos / expedientes

- **pgou-torrelavega.es/noticias**: noticias de tramitación revisión PGOU (aprobación inicial, alegaciones, pleno, etc.).
- **pgou-torrelavega.es/documentos**: bloques documentales (II/III documento PGOU) con PDFs en `/files/pgou/`.
- **SIUCAN**: 11 sectores urbanísticos municipales como filas de referencia con polígono WFS.

No hay listado público de expedientes de licencia/obra individual en HTML estático.

## Licencias

- Sede STA **CATSERV**: trámites `URB_*` (licencias, cédula, parcelación, convenios, etc.) — páginas informativas, no concesiones publicadas.
- Sin dataset de licencias concedidas en tablón (PTS2 vacío sin JS).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** SIUCAN WFS `Urbanismo:Sectores` (GML3 → GeoJSON EPSG:4326); campos `Código_Sector`, `Denominación_Sector`, `Código_INE=39087`.
- **Estrategia:** ingestar sectores WFS como proyectos de referencia; intentar enlazar códigos de sector en títulos PGOU vía regex (`SU-NC`, etc.).
- **Limitaciones:** tablón STA requiere ejecución JS; AUCAN no accesible en CI; PGOU/noticias son PDFs sin georreferencia por expediente; no hay join expediente↔polígono en portal municipal.

## Limitaciones técnicas

- `PTS2_TABLON`: `submitAjax.aa` no expone dataset sin sesión/evento válido; no replicado en adapter.
- Licencias: solo trámites + nota informativa (`min_rows` implícito vía trámites STA).
- User-Agent identificable; `request_delay_s: 0.35`.
