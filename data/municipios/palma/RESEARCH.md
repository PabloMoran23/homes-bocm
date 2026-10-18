# Palma — investigación portal ayuntamiento

## Fuentes

| Rol | URL |
|-----|-----|
| Sede Sedipualba (tablón, catálogo trámites) | https://palma.sedipualba.es |
| Tablón RSS | https://palma.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Tablón HTML | https://palma.sedipualba.es/tablondeanuncios/ |
| Sede Liferay urbanismo | https://seuelectronica.palma.cat/es/urbanismo?categoryId=40315 |
| Tablón Liferay | https://seuelectronica.palma.cat/-/tauler-electr%C3%B2nic-d-edictes-i-anuncis |
| Web municipal / visor | https://www.palma.es/visor-d-urbanisme |
| Área urbanismo | https://urbanisme.palma.es/planejament1 |
| Geoportal IDE Palma | https://geoportal.palma.cat/geonetwork/srv/search?type=service |

## Listado de expedientes / licencias

- **Tablón Sedipualba:** tabla HTML (~30 anuncios visibles) + RSS (20 ítems). Títulos en catalán/castellano; enlaces `anuncio.aspx?id=`.
- **Sede Liferay:** fichas de trámite (`/-/obras.02-licencia-urbanística`, `/-/planeamiento.08-plan-parcial-a-iniciativa-privada`, …). No hay API JSON pública del tablón; las concesiones de licencia no se publican como dataset abierto (solo trámites informativos y edictos).
- **Catálogo Sedipualba área 1551** (Urbanisme): pocos trámites telemáticos; el grueso de planeamiento/obras está en Liferay.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor urbanístico SIGDU: https://www.palma.es/visor-d-urbanisme (documentación por clic en mapa; sin API REST documentada por expediente).
  - WFS IDE Palma: `https://geoportal.palma.es/geoserver/space/ows` — capa `space:INFRCATALOGOPGOU2021` (catálogo infraestructuras PGOU 2021, escala 1:1000).
  - Catálogo metadatos: https://geoportal.palma.cat/geonetwork/srv/api/records/spa_ajpalma_infrcatalogopgou2021
- **Estrategia:** el adapter intenta paginar el WFS en GeoJSON (`EPSG:4326`) y adjunta polígonos a filas del catálogo; para tablón/trámites no hay campo de enlace a geometría → el orquestador usa centroide municipal + jitter.
- **Limitaciones:**
  - Dominios `*.palma.cat` / `*.palma.es` (IP 77.224.171.190) pueden no responder TLS desde algunos entornos cloud (timeout en handshake); Sedipualba (`palma.sedipualba.es`) sí es accesible.
  - El WFS describe planeamiento vigente, no geometría por número de expediente de licencia.

## Notas técnicas

- Boletín autonómico: **BOIB** (`boletin_source_id: boib`); en cola `bocm_count: 0`.
- Certificados: usar `insecure_ssl: true` en manifest para Liferay/geoportal cuando el entorno lo permita.
