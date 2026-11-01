# Esplugues de Llobregat — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Web oficial | https://www.esplugues.cat (WordPress + GeneratePress) |
| Sede electrónica | https://sede.esplugues.cat (Indenova / portal clásico) |
| INE municipio | 08077 |
| Código AMB listados PDF | 08077 |

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Urbanisme (servei) | https://www.esplugues.cat/serveis/urbanisme/ |
| Gestió urbanística | https://www.esplugues.cat/serveis/directori-serveis/servei-de-gestio-urbanistica/ |
| Ordenances / tauler d'anuncis | https://www.esplugues.cat/ajuntament/ordenances-normatives-tauler-anuncis/ |
| Notícies urbanisme (WP cat. 188) | https://www.esplugues.cat/noticies/category/urbanisme/ |
| CIDO (planejament publicat) | https://cido.diba.cat/normativa_local/6638561/planejament-urbanistic-ajuntament-desplugues-de-llobregat |
| Seu-e (govern obert) | https://www.seu-e.cat/ca/web/espluguesdellobregat/ |
| Sede — pestanya urbanisme (8) | https://sede.esplugues.cat/portal/pestana.do?pes_cod=8&ent_id=1&idioma=2 |
| Sede — tabló virtual | https://sede.esplugues.cat/portal/tablonVirtual.do?subseccion=TABLONVIRTUAL&opc_id=175&pes_cod=4&ent_id=1&idioma=2 |
| STA catálogo trámites | https://sede.esplugues.cat/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_CATSERV&lang=CA |
| Visor municipal Enmapa | https://esplugues.enmapa.com/visor/geoportal |
| Geoportal AMB (PDF llistat) | https://geoportalplanejament.amb.cat/Informacio/Llistats_expedients/b/08077_b.pdf |

## Proyectos / expedientes

1. **AMB ArcGIS** — capa `Planejament/Expedients/MapServer/3`, filtro `CODI_INE='08077'`. Devuelve ~184 expedientes con `NOMEXP`, `DGU`, `VIGENT`, `URL` y **polígono** en WGS84. Es la fuente principal del adapter.
2. **WordPress REST** — `wp-json/wp/v2/posts?categories=188` (notícies d'urbanisme); se filtran filas con keywords de planeamiento (se excluye ruido institucional).
3. **Páginas semilla** — enlaces a CIDO y PDFs embebidos en urbanisme / tauler (pocos PDFs directos en HTML).
4. **Listado PDF AMB** — histórico en PDF; no parseado (redundante con GIS).

## Licencias de obra

- No hay dataset abierto de licencias concedidas con coordenadas.
- Trámites en **STA** (`dataset_CATSERV` en PTS_CATSERV) y fichas `literal.do` / `noEstatica.do` en pestaña urbanisme.
- **Tablón virtual** sede (pestanya 4) para edictos; en el entorno del agente `sede.esplugues.cat` respondió vacío/timeout — el adapter usa páginas informativas si el catálogo STA no está disponible.
- Cita prèvia (Google Calendar) para llicències d'obra — solo gestión, sin publicación de concesiones.

## Geometría / visor

- **geometry_status:** `available` (vía AMB; visor Enmapa no automatizable)
- **Fuentes:**
  - ArcGIS REST: `https://geoportal.amb.cat/geoserveisapp/rest/services/Planejament/Expedients/MapServer/3`
  - Campo expediente: `DGU`, nombre: `NOMEXP`, enlace: `URL`
  - Visor Enmapa (`esplugues.enmapa.com`) — Cloudflare; no usable con `urllib` en batch
- **Estrategia:** descarga paginada GeoJSON (`f=geojson`, `outSR=4326`, `returnGeometry=true`) por `CODI_INE=08077`; matching fuzzy por título en filas WP.
- **Limitaciones:** licencias sin geometría; sede puede bloquear/red lenta; certificado SSL de `www.esplugues.cat` requiere `insecure_ssl` en el adapter.

## Limitaciones generales

- SSL intermedio en esplugues.cat (`insecure_ssl: true`).
- Sede y Enmapa inestables desde IP de datacenter.
- Noticias WP mezclan obras públicas y planeamiento; filtro heurístico.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
