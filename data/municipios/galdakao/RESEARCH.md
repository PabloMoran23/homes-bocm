# Galdakao — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Portal principal | https://www.galdakao.eus |
| Urbanismo y obras | https://www.galdakao.eus/urbanismo-obras |
| Planeamiento / revisión PGOU | https://www.galdakao.eus/planeamiento |
| Sede electrónica (espublico gestiona) | https://galdakao.egoitzaelektronikoa.eus |
| Tablón de anuncios | https://galdakao.egoitzaelektronikoa.eus/board |
| Catálogo de trámites | https://galdakao.egoitzaelektronikoa.eus/dossier |
| Registro PUR Bizkaia (Galdakao = id **36**) | https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador |

CMS sede: **espublico gestiona** (Apache Wicket, tablón HTML con tabla de 6 columnas, paginación AJAX «Erakutsi gehiago»). Portal corporativo en `galdakao.eus` (contenido estático de urbanismo; acceso intermitente desde IPs de cloud).

## Cómo se listan expedientes / proyectos

1. **Registro PUR Bizkaia** — POST Liferay `IYBIWPUC` con `select-municipios=36`. Devuelve tarjetas HTML (año, título, enlace `idInstrumento=…`, código entre paréntesis). ~48 instrumentos históricos (PGOU, planes especiales, modificaciones, reparcelaciones).
2. **Tablón sede** — Tabla con expediente, procedimiento, categoría (p. ej. *Hirigintza*), descripción y fecha; documentos en `/preview-document/{uuid}`. Solo la primera página (10 filas) viene en HTML estático; el resto requiere AJAX Wicket.
3. **Web urbanismo** — Listado manual de estudios de detalle, reparcelaciones y modificaciones de unidades de ejecución (UE-BE-3, UECR9, UEZU3, Merkadillo, etc.) usado como semillas documentadas cuando el portal corporativo no responde.

## Licencias de obra

- No hay dataset abierto de concesiones históricas.
- El tablón publica licencias / información pública / comunicaciones en categoría *Hirigintza* (p. ej. actividad clasificada en Erletxe).
- Trámites informativos en catálogo sede: *Obra-lizentzia*, *Obra txikiko lizentziak*, *Obra txikiaren aldez aurreko jakinarazpena*, *Hirigintza informazioa eta ziurtagiriak*.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - `geo.bizkaia.eus` — `PX_Bilbao_Metropolitano_inf` (MapServer): capas de planeamiento del área metropolitana (sin capa dedicada `PX_Galdakao_*` en el catálogo INSPIRE revisado).
  - Campos consultados: `DESCRIPCION`, `ETIQUETA` (LIKE por tokens del título: UE-BE-3, UECR9, ITZAGA, MERKADILLO, …).
  - PUR y tablón: PDF/HTML sin geometría embebida.
- **Estrategia:** tras scrape, query ArcGIS `returnGeometry=true`, `f=geojson`, `outSR=4326` con tokens del instrumento; validar centroide dentro del bbox municipal (~43.23, -2.84 ±0.15°).
- **Limitaciones:** sin enlace expediente→polígono en sede; matching heurístico por texto; muchos instrumentos PUR no tienen polígono único en capas metropolitanas.

## Limitaciones técnicas

- `www.galdakao.eus` puede hacer timeout desde entornos cloud (TLS/conectividad); el adapter tolera fallo y mantiene PUR + sede.
- Tablón: paginación solo vía Wicket AJAX (no API JSON pública).
- PUR Bizkaia: requiere `formDate` dinámico del formulario inicial.
