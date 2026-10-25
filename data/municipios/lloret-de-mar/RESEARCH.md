# Lloret de Mar — investigación portal ayuntamiento

## Fuentes

| Ámbito | URL | Formato |
|--------|-----|---------|
| Web corporativa | https://www.lloret.cat/ca/seccions/planejament-i-gestio-urbanistica | Plone (THEME Ajuntament Lloret) |
| Exposición pública | https://www.lloret.cat/ca/seccions/planejament-i-gestio-urbanistica/exposicio-publica | Índice + subsecciones (instrumentos, gestión, obra ordinaria) |
| Seu electrònica | https://seu.lloret.cat/ | STA / Genesys (mismo stack que otros municipios catalanes) |
| Registre planejament | https://seu.lloret.cat/urbanismeCategoriaPublic/cercadorCategoria/{7,8,34} | HTML paginado (`offset`/`max`, bloques `data-registre-public`) |
| Detalle publicación | https://seu.lloret.cat/registrePublic/registrePublicacio/{id} | Título, fecha, PDFs adjuntos |
| Catàleg tràmits | https://tramits.lloret.org/OAC/CdT.jsp | GWT (`CarpetaTramits.nocache.js`) — solo trámites informativos |
| Carpeta ciudadana | https://tramits.lloret.org/CarpetaCiutada/ | Tramitación online (sin tablón de licencias concedidas) |
| Búsqueda Plone | https://www.lloret.cat/ca/search_rss?SearchableText=planejament | RSS 1.0 |

### Semillas Plone usadas en el adapter

- `.../exposicio-publica` y subcarpetas (`instruments-de-planejament`, `instruments-de-gestio`, `projectes-dobra-ordinaria`)
- `.../planejament-derivat`, `.../projecte-4-estacions`, `.../obres-municipals`

### Registre seu (categorías)

- **7** — publicaciones de planeamiento (paginación `listPublicacionsAmbCategoria?categoria.id=7&offset=&max=`)
- **8** — otra línea de publicaciones urbanísticas
- **34** — publicaciones adicionales (gestión / actuaciones)

Cada fila incluye fecha (`DD/MM/YYYY`), enlace a `registrePublicacio/{id}` y título en `<div class="top"><p>…</p>`.

## Licencias de obra

No hay tablón público de licencias concedidas con dirección/coordenadas. El catálogo `tramits.lloret.org` carga trámites vía GWT sin listado scrapeable en HTML estático. El adapter devuelve **páginas informativas** del catálogo y serveis d'urbanisme (patrón Pozuelo/Lleida) y filtra del registre seu entradas cuyo título menciona licencias/obras.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - AMB `Planejament/Expedients` MapServer capa 3 con `CODI_INE='17095'` → 0 features (municipio fuera del ámbito metropolitano con datos de expedientes AMB).
  - Web lloret.cat: enlaces a PDF de mapas estáticos (`lloretdemar.org/images/MAPA A3 2016.pdf`), sin visor ArcGIS/WFS enlazado a expedientes.
  - Seu: publicaciones con PDFs de planeamiento sin geometría machine-readable.
- **Estrategia:** el orquestador aplicará `centroid` del manifest + jitter en geocode.
- **Limitaciones:** sin WFS/GeoJSON municipal público; sin join expediente ↔ polígono.

## Limitaciones generales

- RSS de búsqueda Plone mezcla notas de prensa de obras con planeamiento; el adapter filtra por palabras clave.
- Paginación del registre seu vía `categoria.id` + `offset`/`max` (no usar solo `cercadorCategoria/{id}` sin query, devuelve siempre la primera página).
- Catálogo de trámites no expone listado HTML de licencias históricas.
