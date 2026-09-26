# Brea de Tajo — investigación portal ayuntamiento

Municipio de la Comunidad de Madrid (código SITCM 025, ~541 hab.). Asesoramiento urbanístico compartido vía mancomunidad MISECAM.

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web corporativa | https://breadetajo.es | WordPress (tagDiv/Newspaper); sin sección urbanismo dedicada |
| Ordenanzas | https://breadetajo.es/ordenanzas-municipales/ | 33 PDFs ordenanzas fiscales + impresos trámites |
| Impresos licencia | https://www.breadetajo.es/pdf/solicitud_licencia_urbanistica.pdf | Solicitud licencia urbanística |
| Declaración responsable | https://www.breadetajo.es/pdf/declaracion_responsable.pdf | DR urbanística |
| Instancia general | https://www.breadetajo.es/pdf/instancia_general.pdf | Instancia general |
| Ordenanza licencia | https://breadetajo.es/pdf/7_licencia_urbanistica.pdf | Tasa licencia urbanística |
| Sede eAdmin | https://sedebreadetajo.eadministracion.es | Maggioli SPA; tablón en `/PortalCiudadano/Tablon/wfrTablon.aspx` |
| Sede legacy | https://breadetajo.sedelectronica.es | espublico; **inactiva** («En Construcción») |
| MISECAM urbanismo | https://misecam.org/urbanismo/ | Oficina técnica mancomunada; atención martes 12:00-14:00 |
| Visor SITCM | https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=025 | Planeamiento CM |

## Cómo se listan expedientes / proyectos

- **No hay visor ni listado propio** de expedientes en la web municipal.
- **Planeamiento histórico:** Normas Subsidiarias «Matriz» aprobadas 1987 (BOCM 1987-11-11, BOE 1987-11-17) con 7 Unidades de Actuación (UA-1…UA-7) publicadas en **SITCM** (WFS Comunidad de Madrid).
- **Tablón de anuncios:** sede eAdmin (`wfrTablon.aspx` o `eAdmin/Tablon.do`); **502 Bad Gateway** desde el entorno del agente (reintentar en local).
- **Sede legacy** espublico inactiva; sin documentos en `/board` ni `/transparency`.
- **WordPress REST API** (`/wp-json/wp/v2/posts`) accesible; pocos posts urbanísticos (noticia MISECAM 2023-05-22).

## Cómo se publican licencias

- **Sin tablón público accesible** en el momento de la investigación.
- **Impresos descargables** en web corporativa (solicitud licencia, DR, instancia general).
- **Ordenanza fiscal** de licencia urbanística (PDF nº 7).
- **Trámites presenciales** martes 12:00-14:00 con cita previa (MISECAM/ayuntamiento).
- No hay dataset ni RSS de concesiones de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer CM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='BREA DE TAJO'`
  - Campo ámbito: `DS_NOMB_AMB` (UA-1 … UA-7)
  - Visor: `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=025`
- **Estrategia:** descarga WFS por municipio; enriquecer filas con código UA en título; polígonos en EPSG:4326 vía `returnGeometry` implícito en `outputFormat=application/json`.
- **Limitaciones:**
  - Solo 7 ámbitos de Normas Subsidiarias 1987; sin geometría por expediente individual.
  - Sede eAdmin inaccesible (502); sin enlace expediente→GIS.
  - Licencias publicadas solo como impresos PDF, sin coords.

## Limitaciones generales

- Municipio pequeño sin sección urbanismo en web; dependencia MISECAM para asesoramiento.
- Sede eAdmin y sede legacy no operativas desde CI.
- Sin datos abiertos propios ni API de expedientes.
- Paginación WP REST estándar (≤500 posts).
