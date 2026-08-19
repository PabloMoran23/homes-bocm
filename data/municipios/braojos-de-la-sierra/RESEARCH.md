# Braojos de la Sierra — investigación portal ayuntamiento

**Municipio:** Braojos de la Sierra (Comunidad de Madrid)  
**Fecha:** 2026-08-15  
**BOCM regional (referencia):** 3 avisos

## Resumen

Braojos de la Sierra publica normativa urbanística y el avance del PGOU en su **web municipal Joomla**
(`braojos.org`, plantilla Helix Ultimate + SP Page Builder) y gestiona trámites en la **sede electrónica
espublico gestiona** (`braojos.sedelectronica.es`). Los ámbitos de planeamiento están en el
**SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`, código municipio 024).

**Nota:** El dominio `braojosdelasierra.es` no resuelve; la web oficial es `braojos.org`.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web corporativa | `https://braojos.org` | Joomla Helix | Menú normativa, tablón, trámites |
| Avance PGOU | `https://braojos.org/tu-ayuntamiento/normativa-municipal/avance-plan-general` | Joomla + PDFs | 11 documentos PGOU (memorias, planos, BOCM, IPAT) |
| Planeamiento | `https://braojos.org/tu-ayuntamiento/normativa-municipal/planeamiento-urbanistico` | Joomla | Enlace visor SITCM municipio 024 |
| Ordenanzas | `https://braojos.org/tu-ayuntamiento/normativa-municipal/ordenanzas-municipales` | Joomla artículos | Ordenanza tramitación licencias, ocupación vía pública, IIVTNU… |
| Tablón municipal | `https://braojos.org/ciudadanos/tablon-municipal` | Joomla icagenda + RSS | Anuncios municipales (PGOU aprobación provisional, etc.) |
| Bandos alcaldía | `https://braojos.org/tu-ayuntamiento/alcaldia/bandos-de-alcaldia` | Joomla + RSS | Consultas urbanísticas PGOU, licencias suelo rústico, ocupación vía |
| Licencias / trámites | `https://braojos.org/ciudadanos/tramites-personales/instancias-licencias-y-solicitudes` | Joomla + PDFs | Modelos obra mayor/menor, DR, vallado finca rústica |
| Tablón sede | `https://braojos.sedelectronica.es/board/` | HTML espublico | Tablón de anuncios (vacío en CI, agosto 2026) |
| Transparencia | `http://transparencia.braojos.org/` | Portal externo | Documentación administrativa |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 2 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='BRAOJOS'` |
| Visor SIT | `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=024` | ArcGIS web | Enlace desde página Planeamiento urbanístico |

## Cómo se listan expedientes

- **Planeamiento:** PDFs del avance PGOU en página dedicada (`/media/attachments/2023/...`).
  Anuncio de aprobación provisional en tablón municipal (`/ciudadanos/tablon-municipal/615-...`).
- **Bandos:** artículos Joomla en `/tu-ayuntamiento/alcaldia/bandos-de-alcaldia` con feed RSS.
- **Ordenanzas:** listado Joomla con artículos individuales y PDF embebido (p. ej. ordenanza licencias).
- **Tablón sede:** tabla HTML espublico (actualmente sin filas publicadas).
- **No hay** visor urbanístico propio del ayuntamiento ni API JSON de expedientes.

## Licencias

- Modelos PDF en `/ciudadanos/tramites-personales/instancias-licencias-y-solicitudes`
  (obra mayor, obra menor, declaración responsable, vallado).
- Ordenanza de tramitación de licencias (PDF en `/images/Ordenanzas/...`).
- No hay dataset histórico de concesiones con coordenadas.
- Anuncios de licencia aparecerían en tablón municipal o sede cuando se publiquen.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='BRAOJOS'` (`CD_MUNICIPIO=024`, `srsName=EPSG:4326`)
  - Visor SIT CM: `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=024`
  - 2 ámbitos: `UE-1 NORESTE`, `UE-2 TRAVESIA ERAS` (suelo urbano)
- **Estrategia:** Semillas de ámbitos desde WFS con `geom_geojson`; enriquecer proyectos Joomla
  cuando el título contiene código UE o nombre de ámbito SIT.
- **Limitaciones:** Solo 2 ámbitos en SITCM; PDFs PGOU sin georreferenciación directa;
  licencias solo como formularios informativos; tablón sede vacío; `resolve_municipio_wfs('Braojos de la Sierra')`
  falla porque el nombre en SIT es `BRAOJOS` (sin «de la Sierra»).

## Limitaciones

- Dominio `braojosdelasierra.es` inactivo; usar `braojos.org`.
- Tablón sede espublico sin anuncios activos en el momento de la investigación.
- Licencias solo como páginas de trámite, sin concesiones publicadas con coordenadas.
- Municipio pequeño con escaso planeamiento publicado online (PGOU en tramitación).

## Estrategia adapter

1. Parsear PDFs del avance PGOU y ordenanzas urbanísticas Joomla.
2. Feeds RSS de bandos y tablón municipal.
3. Semillas de ámbitos SIT WFS (2 UEs) con `geom_geojson`.
4. Tablón sede espublico + páginas informativas y formularios de licencias.
5. IDs: `braojos-de-la-sierra-{lic|proy}-{sha256[:14]}`.
