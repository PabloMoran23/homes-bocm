# Guadalix de la Sierra — investigación portal ayuntamiento

## Resumen

Municipio de la Comunidad de Madrid (Sierra Norte). El ayuntamiento publica urbanismo principalmente vía **normas subsidiarias** (enlace al visor SITCM) y documentación en el portal de transparencia. La **sede electrónica** (`eadministracion.es`) es una SPA Angular sin tablón scrapeable. Los **modelos de solicitud** (Phoca Download) cubren trámites de licencias urbanísticas.

## URLs base y páginas semilla

| Recurso | URL | Formato | Uso |
|---------|-----|---------|-----|
| Web corporativa | `https://www.guadalixdelasierra.com` | Joomla 3 | Portal principal |
| Normas subsidiarias | `/index.php/portal-de-transparencia/normas-subsidiarias` | HTML | Enlace visor SITCM |
| Ordenación del territorio | `/index.php/portal-de-transparencia/informacion-trasparencia/informacion-ordenacion-del-territorio` | HTML (vacío) | Sin documentos |
| Publicaciones BOCM | `/index.php/portal-de-transparencia/publicaciones-en-boletines-oficiales` | Phoca Download (paginado) | PDFs publicados en BOCM |
| Modelos de solicitud | `/index.php/modelos-de-solicitud` | Phoca Download (32 formularios) | Trámites licencias/urbanismo |
| Sede electrónica | `https://guadalixdelasierra.eadministracion.es/home` | Angular SPA | Trámites online; sin listado público scrapeable |
| Visor SITCM | `https://www.madrid.org/cartografia/sitcm/html/visor.htm` | Visor web | Planeamiento CCAA |

## Cómo se listan expedientes / proyectos

- **No hay listado de expedientes urbanísticos** en la web municipal ni en la sede.
- **NNSS:** página informativa que remite al visor SITCM de la Comunidad de Madrid.
- **BOCM:** Phoca Download con ~60 PDFs (ordenanzas, notificaciones); solo 1 entrada claramente urbanística (tasa servicios urbanísticos).
- **Ámbitos de planeamiento:** publicados en el WFS SITCM (`sitcm:VPLA_V_AMBITO`) — 50 polígonos para el municipio (UE, SAU, SG, PERI).

## Cómo se publican licencias

- **No hay dataset ni tablón** de licencias concedidas con dirección o coordenadas.
- **Modelos de solicitud:** formularios PDF (obra mayor/menor, calificación urbanística, declaraciones responsables, etc.) — páginas informativas de trámite.
- **Sede eAdmin:** trámites presenciales/telefónicos; sin API ni HTML de concesiones.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='GUADALIX DE LA SIERRA'`
  - Campo ámbito: `DS_NOMB_AMB` (ej. `UE-22 EL CALLEJÓN`, `SAU-8 INDUSTRIAL CARRETERA DE NAVALAFUENTE ESTE`)
  - Visor web: `https://www.madrid.org/cartografia/sitcm/html/visor.htm`
- **Estrategia:** descargar todos los ámbitos del municipio vía WFS GetFeature (`outputFormat=application/json`, `srsName=EPSG:4326`); enriquecer proyectos cuyo título contenga código UE/SAU/SG/PERI con `resolve_ambito_geometry`.
- **Limitaciones:**
  - Geometría solo para ámbitos de planeamiento (no licencias individuales ni expedientes).
  - Sede eAdmin y tablón municipal no accesibles para scrape.
  - Páginas NNSS/ordenación sin PDFs descargables.

## Limitaciones generales

- Sede `eadministracion.es` es SPA; no hay tablón HTML como en sedes espublico.
- Phoca Download paginado (20 ítems/página); sin API JSON.
- Sin visor urbanístico propio del ayuntamiento; dependencia del SITCM regional.
- SSL válido en web y sede.

## Adapter

- Módulo: `municipio/adapters/guadalix_de_la_sierra.py`
- Fuentes: SITCM WFS (ámbitos) + Phoca BOCM/modelos + páginas informativas NNSS/sede.
