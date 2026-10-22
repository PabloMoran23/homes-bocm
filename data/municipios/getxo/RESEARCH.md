# Getxo — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|--------|
| Web | https://www.getxo.eus |
| Sede | https://sede.getxo.eus (nueva e-sede); legado en /es/sede-electronica |
| Urbanismo | https://www.getxo.eus/es/desarrollo-urbanistico-sostenible/pgou/ |
| e-Tablón | https://eudala.getxo.eus/WEBTablon/MenuTablon.aspx?ChangeIdioma=CA |
| CMS | ASP.NET municipal (getxo.eus) + aplicación eudala (tablón, contratación) |

## Fuentes de proyectos / planeamiento

1. **PGOU y revisiones** — sección *Desarrollo urbanístico sostenible → PGOU*: documentos en `DocsPublic/urbanismo/` (modificaciones puntuales, BOB, acuerdos de pleno, PGOU 2026, etc.).
2. **e-Tablón — Urbanismo** — `AnunciosWEB.aspx?opt=URBA&int=1&OpcionMNU_Llamado=560` (ASP.NET GridView; documentos vía postback, metadatos en tabla HTML).
3. **e-Tablón — Todos** — `opt=TO` filtrado por palabras clave urbanísticas (complemento cuando URBA está vacío).
4. **Participación PGOU** — https://hapo-getxo.eus (documentación histórica de revisiones; enlazada desde la web principal).

No hay listado público tipo “expedientes en información pública” con fichas enlazadas (modelo Pozuelo). La sede permite consulta de expedientes con identificación.

## Licencias de obra

- **Tablón URBA**: edictos de licencias cuando se publican (a menudo vacío en campaña actual).
- **Guía de trámites**: https://www.getxo.eus/es/tramites/tramitesnew — procedimientos del departamento Urbanismo (sin URL por trámite; atención presencial / sede).
- No se encontró dataset ni tabla de licencias concedidas con coordenadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Lizmap PGOU: `https://eudala2.getxo.eus/lizmap/www/index.php/view/map/?repository=pgou&project=pgou&lang=es_es` — capas del planeamiento aprobado, sin campo de expediente/licencia.
  - Open data territorio: https://www.getxo.eus/es/gobierno-abierto/opndata/territorio — sin WFS de expedientes urbanísticos.
  - Diputación / ArcGIS metropolitano (capas PGOU Bizkaia) — ámbitos de planeamiento, no expedientes del ayuntamiento.
- **Estrategia adapter:** no implementar `_fetch_geometry`; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** documentación mayoritariamente PDF; visor PGOU no enlaza a expedientes administrativos.

## Limitaciones técnicas

- e-Tablón codificación ISO-8859-1; descarga de PDFs del tablón requiere POST ASP.NET (`__VIEWSTATE`).
- Planos PGOU masivos (`pgap-*.pdf`) excluidos del crawl para evitar cientos de filas duplicadas; se priorizan modificaciones y resoluciones en `DocsPublic/urbanismo`.
- `bocm_count: 0` — sin boletín regional asociado en la cola.

## Semillas implementadas

Ver `manifest.yaml` → `seed_pages` y URLs de tablón en `municipio/adapters/getxo.py`.
