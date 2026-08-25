# Ribatejada — investigación portal ayuntamiento

**Municipio:** Ribatejada (Comunidad de Madrid)  
**Fecha:** 2026-08-22  
**BOCM regional (referencia):** 3 avisos

## Resumen

Ribatejada publica información municipal en web WordPress (tema BeTheme) y gestiona trámites en sede electrónica **sedipualba**. No dispone de sección dedicada de urbanismo en la web ni visor municipal propio. El planeamiento vigente (unidades de actuación UA) se consulta en el visor SIT de la Comunidad de Madrid.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web oficial | `https://www.ribatejada.es` | WordPress BeTheme | Bandos, ordenanzas PDF |
| Bandos municipales | `https://www.ribatejada.es/bandos-municipales/` | HTML listado posts | Proyectos filtrados |
| Ordenanzas | `https://www.ribatejada.es/ordenanzas/` | HTML + PDF | Aprobación inicial BOCM (ordenanza festejos) |
| WP REST API | `https://www.ribatejada.es/wp-json/wp/v2/posts` | JSON | Posts con keywords urbanismo |
| Sede sedipualba | `https://ribatajada.sedipualba.es/` | ASP.NET | Tablón + catálogo trámites |
| Tablón RSS | `https://ribatajada.sedipualba.es/tablondeanuncios/tablon_rss.aspx` | RSS ISO-8859-1 | Anuncios (vacío ago 2026) |
| Instancia general | `https://ribatajada.sedipualba.es/carpetaciudadana/tramite.aspx?idtramite=14403` | Trámite sede | Licencias informativas |
| Visor SIT CM | `https://www.madrid.org/cartografia/sitcm/html/visor.htm` | ArcGIS/WFS | Ámbitos UA con polígono |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` | GeoJSON WFS | Geometría ámbitos (`DS_MUNICIPIO='RIBATEJADA'`) |

## Fuentes detalladas

### 1. Web corporativa — WordPress BeTheme

- **URL base:** `https://www.ribatejada.es`
- **CMS:** WordPress 6.8 + tema BeTheme
- **Secciones relevantes:**
  - `bandos-municipales/` — listado de bandos (mayoría protocolos, cobranzas, fiestas)
  - `ordenanzas/` — PDFs de ordenanzas; incluye publicación BOCM aprobación inicial (oct 2025)
  - `servicios-al-ciudadano/punto-de-informacion-catastral/` — enlace informativo catastro
- **Sin sección** dedicada a urbanismo, PGOU, licencias ni visor cartográfico propio.

### 2. Sede electrónica — sedipualba

- **URL:** `https://ribatajada.sedipualba.es/`
- **CMS:** sedipualba (ASP.NET)
- **Tablón de anuncios:** `tablondeanuncios/` + RSS `tablon_rss.aspx`
- **Estado ago 2026:** RSS devuelve «No hay anuncios»; tablón vacío
- **Catálogo trámites:** Solo «Registro Electrónico / Presentación Instancia General» (`idtramite=14403`); sin trámites urbanísticos específicos publicados
- **Nota:** La sede muestra dirección errónea (Cuenca) en metadatos sedipualba; el municipio es de Madrid (INE 28141)

### 3. Planeamiento y geometría — SIT Comunidad de Madrid

- **Visor:** `https://www.madrid.org/cartografia/sitcm/html/visor.htm`
- **WFS capa:** `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='RIBATEJADA'`
- **Ámbitos detectados (11):**
  - UA-1 PASEO DEL PINAR-ESTE
  - UA-2 PALACIO
  - UA-3 TRAVESÍA DEL PALACIO
  - UA-4 CERRO DE LOS SANTOS
  - UA-5 PASEO DEL PINAR-OESTE
  - UA-6 CALLE RIBAPINADA
  - UA-7 LAS POZAS
  - UA-8 CAÑADA
  - UA-9 URBANIZACIÓN LOS CERRRILLOS
  - UA-10 POLÍGONO INDUSTRIAL
  - PARAJE DEL ARZOBISPO
- **Campos:** `DS_NOMB_AMB`, geometría polígono EPSG:4326

### 4. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `ribatejada.sedelectronica.es` | No responde / dominio alternativo inactivo |
| BOCM re-parse | Ya en pipeline regional |
| Expedientes sede | Requiere identificación; sin listado público |
| Visor urbanístico municipal | No existe |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid IDEM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='RIBATEJADA'`
  - Campo ámbito: `DS_NOMB_AMB` (UA-1 … UA-10, PARAJE DEL ARZOBISPO)
  - Visor público: `https://www.madrid.org/cartografia/sitcm/html/visor.htm`
- **Estrategia:** Importar los 11 polígonos WFS como proyectos de planeamiento; cruzar títulos de anuncios/PDF con código UA cuando aparece en el texto.
- **Limitaciones:**
  - Sin visor urbanístico municipal ni geometría por expediente individual.
  - Tablón sede vacío; sin licencias concedidas publicadas.
  - Web sin documentación PGOU/NNSS indexable (solo ordenanza festejos con BOCM).
  - Geometría disponible solo para ámbitos del planeamiento regional, no para licencias puntuales.

## Limitaciones generales

- Municipio pequeño (~2.000 hab.); publicación urbanística mínima.
- Tablón sedipualba sin anuncios vigentes.
- Licencias: solo trámite genérico de instancia; sin listado de concesiones.
- Fechas inferidas de URL PDF, año en slug o metadatos WP cuando no hay fecha explícita.
