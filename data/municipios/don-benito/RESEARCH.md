# Don Benito — investigación portal ayuntamiento

Municipio: **Don Benito** (`don-benito`)  
Provincia: Badajoz · CCAA: Extremadura  
Código INE municipio: `06044`

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.donbenito.es/ | Portal corporativo (SPA, poco contenido urbanístico indexable) |
| Sede electrónica (Galileo GIYS) | https://sede.donbenito.es/ | Trámites, edictos, tablón, transparencia |
| Catálogo procedimientos | https://sede.donbenito.es/publico/procedimientos | Materia **URBANISMO** (17 procedimientos; listado vía postback ASP.NET) |
| Tablón edictos | https://sede.donbenito.es/publico/tablon | Anuncios con enlace `/publico/edictos/{id}` |
| Edictos RSS | https://sede.donbenito.es/publico/sindicacion/edictos/RSS | Sindicación XML (pocos ítems activos) |
| Ordenanzas RSS | https://sede.donbenito.es/publico/sindicacion/ordenanzas/RSS | Ordenanzas municipales |
| Informe urbanístico | https://sede.donbenito.es/publico/territorio/informeurbanistico | Texto informativo + visor embebido (postback) |
| Mapa municipal | https://sede.donbenito.es/publico/mapa | Mapa sede (sin API ArcGIS pública documentada) |
| IDE Diputación Badajoz | http://sigcba.dip-badajoz.es/geoportal/Don%20Benito | IDE municipal (infraestructuras; no expedientes) |
| IDE Extremadura urbanismo WMS | http://www.ideextremadura.com/CICTEX/urbanismo | Capas regionales (suelo, UA) sin código expediente ayto |

## Cómo se listan expedientes / proyectos

- **Tablón / edictos:** HTML en sede + RSS. Cada edicto tiene página de detalle con número de expediente (p. ej. `2025000008`), procedencia (URBANISMO), PDFs adjuntos.
- **Ejemplo urbanístico:** exposición pública proyecto módulo de nichos cementerio municipal (nov 2025).
- **Catálogo trámites:** categoría URBANISMO accesible solo con postback; no hay API JSON pública.
- **No hay** visor de expedientes urbanísticos con listado tabular histórico ni consulta por código en GIS municipal.

## Cómo se publican licencias

- **No hay** listado público de licencias concedidas con ubicación ni coordenadas.
- Trámites de licencia/obra en catálogo URBANISMO (sede); ejecución vía carpeta ciudadana.
- Edictos pueden incluir anuncios de urbanismo pero no un registro sistemático de concesiones.
- El adapter devuelve páginas informativas de trámites + edictos filtrados; `min_rows: 0` aceptable para licencias reales.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** WMS IDE Extremadura (`CICTEX/urbanismo`); visor sede `/publico/mapa` y capas en informe urbanístico (JavaScript/postback); geoportal Diputación Badajoz.
- **Estrategia:** ninguna capa pública enlaza geometría de parcela/expediente con el código del tablón (`2025000008`). Solo planeamiento regional agregado.
- **Limitaciones:** edictos en PDF/HTML; visor municipal no expone MapServer consultable por expediente; datos abiertos RSS vacío.

## Limitaciones generales

- RSS edictos con historial limitado (solo anuncios vigentes).
- Procedimientos urbanismo requieren postback (no scrapeable sin sesión).
- Sin boletín regional asociado en cola (`bocm_count: 0`).
- El orquestador usará centroide municipal + jitter para coordenadas.
