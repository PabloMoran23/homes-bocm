# Ambite — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (Neosoft) | https://www.ambite.es | CMS corporativo Neosoft Sistemas |
| Urbanismo | https://www.ambite.es/servicios-urbanisticos | Normas Subsidiarias, planos, ordenanza licencias (PDF) |
| Instancias y trámites | https://www.ambite.es/instancias-y-tramites | Formularios licencia/DR urbanística (cms.ambite.es) |
| Normativa | https://www.ambite.es/normativa | Ordenanzas generales |
| Sede espublico | https://ambite.sedelectronica.es | Tablón de anuncios, transparencia |
| Tablón de anuncios | https://ambite.sedelectronica.es/board | Anuncios IP, contratación obra pública |
| Geoportal CAM | https://www.comunidad.madrid/servicios/atencion-ciudadano/geoportal | Referencia en web; datos vía WFS IDEM |

## Listado de expedientes / proyectos

- **Urbanismo (Neosoft):** página `/servicios-urbanisticos` con acordeón de PDFs en `/Ficheros/Documentos/*.pdf` (NNSS 2022 BOCM, planos SNU/zonas A-B, modificaciones puntuales UE, ordenanza licencias).
- **Tablón sede (espublico):** tabla HTML `<tbody>` con `preview-document/{uuid}`; columnas documento, expediente, procedimiento, categoría, descripción, fecha.
- **Noticias web:** ocasionalmente urbanismo (p. ej. compra solar Calle Mediodía) — no indexadas en sección dedicada.

## Licencias

- No hay dataset público de concesiones con dirección/coords.
- `/instancias-y-tramites` enlaza formularios PDF (licencia urbanística, declaración responsable, actividad) en `cms.ambite.es/Ficheros/Documentos/`.
- Tablón sede puede incluir anuncios de licencia puntuales (filtrados por regex).
- Trámites reales vía sede espublico.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid IDEM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='AMBITE'`
  - Campo ámbito: `DS_NOMB_AMB` (12 polígonos: UE-01…UE-10, UE-02.A/B, S-01R)
- **Estrategia:** ingestar ámbitos SIT como filas de planeamiento con `geom_geojson`; cruzar título de anuncio/PDF con código UE/S si aparece en el texto.
- **Limitaciones:**
  - Sin visor urbanístico municipal ni ArcGIS por expediente.
  - Licencias y anuncios puntuales (embellecimiento viario, canon Tajera) sin polígono en WFS.
  - Sede espublico requiere `insecure_ssl` (cadena TLS intermedia).
  - PDFs del tablón sin georreferencia embebida.

## Limitaciones generales

- Municipio pequeño (~800 hab.); pocos anuncios en tablón.
- CMS sirve PDFs desde `www.ambite.es` y `cms.ambite.es` (mismo patrón Neosoft).
- Fechas inferidas de nombres BOCM (`BOCM-YYYYMMDD`) o celdas del tablón (`DD/MM/YYYY`).
