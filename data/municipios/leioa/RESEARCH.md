# Leioa — investigación portal ayuntamiento

Municipio: **Leioa** (`leioa`), Bizkaia, Euskadi. Sin boletín BOCM asociado en cola.

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.leioa.net |
| Sede electrónica (STA T-Systems) | https://udaletxean.leioa.eus/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME&lang=ES |
| Tablón de anuncios | https://udaletxean.leioa.eus/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES |
| Catálogo de trámites | https://udaletxean.leioa.eus/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES |
| Transparencia (IP urbanismo) | https://leioazabalik.leioa.net/expedientes-del-area-de-urbanismo-en-exposicion/informacion-publica |
| PGOU (transparencia) | https://leioazabalik.leioa.net/plan-general-de-ordenacion-urbana-pgou-.-modificaciones.-normas-urbanisticas.-informes |
| Urbanismo (transparencia) | https://leioazabalik.leioa.net/urbanismo-y-obras-publicas |

## Expedientes / proyectos

1. **Portal transparencia (Liferay):** tabla HTML en la página de expedientes en exposición/información pública. Columnas: título, código expediente (`YYYY/NNNNX`), medio, fechas, enlaces a PDFs en `/documents/...`. ~50 filas históricas accesibles con User-Agent identificable (403 sin UA).
2. **Tablón sede:** JSON embebido `var dataset_PTS_TABLON = [...]` (no `PTS2_TABLON`). Campos útiles: `descriptionProc`, `externString` (código), `pubDateIni`, `dboid` para detalle.
3. **PGOU:** documentación estática (PDFs) en transparencia; no listado dinámico de expedientes en curso.

## Licencias

- El tablón publica pocas licencias explícitas (p. ej. licencias de actividad clasificada).
- **Catálogo STA (`dataset_CATSERV`):** trámites de comunicación previa, licencia de obra mayor/menor, consultas urbanísticas, etc. — páginas informativas (sin listado de concesiones individuales).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor regional Diputación Foral de Bizkaia (ArcGIS REST): `PX_Bilbao_Metropolitano_inf` — ámbitos de planeamiento, clasificación del suelo, etc. (https://www.bizkaia.eus/es/tema-detalle/-/edukia/dt/1813)
  - Planos PGOU municipales solo en PDF (transparencia), sin WFS/WMS municipal dedicado.
- **Estrategia:** en el adapter, búsqueda textual (`ETIQUETA`/`DESCRIPCION LIKE`) sobre capas 100, 119–122, 134 del MapServer de Bizkaia; sin campo de enlace al código de expediente municipal (`2020/2190W`, etc.).
- **Limitaciones:** no hay visor municipal con geometría por expediente; el SIG foral describe ámbitos/sectores del PGOU pero las etiquetas no coinciden de forma fiable con los títulos del tablón/transparencia. El orquestador aplicará centroide municipal + jitter cuando no haya polígono.

## Limitaciones técnicas

- Transparencia `leioazabalik.leioa.net` puede devolver 403 a clientes sin User-Agent.
- Tablón en euskera por defecto; parámetro `lang=ES` recomendado.
- Contenido bilingüe (euskera/castellano) en títulos del tablón.
