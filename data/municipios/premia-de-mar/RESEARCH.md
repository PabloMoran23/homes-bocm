# Premià de Mar — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `premia-de-mar` |
| INE | `08172` |
| Web | https://premiademar.cat (CMS Ample24) |
| Seu-e | https://seu-e.cat/ca/web/premiademar |
| OVAC | https://premiademar.cat/ovac → https://www.epremia.net/ovac |

## Fuentes — proyectos / planeamiento

| URL | Tipo | Notas |
|-----|------|-------|
| https://premiademar.cat/urbanisme-espai-public | HTML Ample24 | Destaca anuncios recientes (`document.php?id=…`) con titular en el enlace |
| https://premiademar.cat/organisme.php?id=173 | HTML | Planejament i gestió urbanística |
| https://premiademar.cat/organisme.php?id=134 | HTML | Regidoria d'Urbanisme; enlace visor OVAC IT |
| https://premiademar.cat/document.php?id=13517 | HTML | Avisos i anuncis vigents (listado) |
| https://seu-e.cat/.../urbanisme/planejament-urbanistic | Liferay AOC | Texto + enlaces RPUC/MUC |
| https://seu-e.cat/.../urbanisme/informacio-geografica-d-urbanisme | Liferay AOC | Deriva al mapa TecnoGeoWS |
| https://seu-e.cat/.../tauler-d-edictes-i-anuncis | Liferay AOC | Edictos (DataTables, sin API simple) |
| https://dtes.gencat.cat/rpucportal/...municipiSel=08172 | RPUC | Expedientes de planeamiento autonómico |
| https://ptop.gencat.cat/muc-visor/...municipi=08172 | MUC | Cartografía urbanística |

Ejemplos de anuncios urbanísticos en portada de urbanisme (nov 2026):

- Avantprojecte comissaria Policia Local (`document.php?id=38324`)
- Projecte aparcament bicicletes (`document.php?id=38322`)
- Illa de vianants Jacint Verdaguer (`document.php?id=38226`)

Muchas fichas `document.php` comparten título genérico (“Avisos i anuncis vigents”); el adapter usa el texto del enlace de listado y, si hace falta, el `<span>` interior.

## Fuentes — licencias

| URL | Tipo | Notas |
|-----|------|-------|
| https://premiademar.cat/ovac | OVAC | Trámites en línea (sin listado público de concesiones) |
| https://premiademar.cat/oac | HTML | OAC + enlace OVAC |
| https://premiademar.cat/organisme.php?id=169 | HTML | Llicències i tràmits |
| Catálogo seu-e `/tramits/.../urbanisme` | Liferay | Sin ítems parseables en el HTML estático (SPA) |

No hay tablón de licencias concedidas con coordenadas. El adapter registra páginas informativas de trámites (patrón Ripollet/Calafell).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Mapa interactiu municipal (TecnoGeoWS):  
    `https://citymap.tecnogeows.com/user/101686710051132607418/map/6rj3V3dnqKpjfnhNtxynou?tree=stage`  
    (enlace desde transparència → informació geogràfica d'urbanisme). SPA con `search.tecnogeows.com`; sin API REST documentada por expediente.
  - Visor IT OVAC:  
    `https://www.epremia.net/ovac/catala/VisorITs/24891A1DA10F4DF6B76E636E84F11358.asp`
  - MUC / RPUC Generalitat (consulta por municipio INE 08172).
  - Capa AMB `Planejament/Expedients/MapServer/3` con `COD_INE='08172'`: **0 features** en prueba (nov 2026).
- **Estrategia:** ingestar metadatos desde web + seu-e; geocode con centroide municipal + bbox manifest. No se rellena `geom_geojson` por fila (visores no enlazables al anuncio concreto).
- **Limitaciones:** PDFs y anuncios sin georreferencia embebida; citymap TecnoGeoWS sin query por código de expediente; tauler d'edictes Liferay sin feed RSS/WFS.

## Limitaciones generales

- Codificación ISO-8859-1 en web Ample24.
- `robots.txt` impone `Crawl-delay: 15` (el adapter usa `request_delay_s: 0.35` en entorno de pipeline controlado).
- Sin boletín BOCM asociado en cola (`bocm_count: 0`).
