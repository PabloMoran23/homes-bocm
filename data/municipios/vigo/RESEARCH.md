# Vigo — portal ayuntamiento

## Fuentes base

| Recurso | URL |
|---------|-----|
| Sede electrónica | https://sede.vigo.org |
| Taboleiro (anuncios / edictos) | https://sede.vigo.org/expedientes/taboleiro/ |
| Exposición pública — Xerencia Urbanismo | https://sede.vigo.org/expedientes/taboleiro/exposicion.jsp?id=1&lang=es |
| Listados por tipo (`ent=0..6`) | `exposicion_listado.jsp?epi=1&ent={ent}&id=1&lang=es` |
| Detalle documento (ODT/PDF) | `fichero_exposicion.jsp?id_archivo={n}&lang=es` |
| Catálogo trámites (licencias OB/CP) | https://sede.vigo.org/expedientes/tramites/tramites.jsp?lang=es |
| Búsqueda trámites | `tramitesbusqueda.jsp?q=...&buscar=SI&lang=es` |
| Planeamiento vigente (PGOM 2025) | https://hoxe.vigo.org/movemonos/urbanismo_pxom_2025.php?lang=cas |
| Datos geográficos / visores | https://mapas.vigo.org , https://mapas-vigo.opendata.arcgis.com/ |

## Proyectos / expedientes

- La **Gerencia Municipal de Urbanismo** publica expedientes en **exposición pública** en el taboleiro de la sede.
- Tipos enlazados desde `exposicion.jsp`: convenios (`ent=0`), operacións xurídicas complementarias (`ent=1`), ordenanzas (`ent=2`), varios urbanísticos (`ent=5`, `ent=6`). Se excluye `ent=3` (personal) y `ent=4` (publicacións non BOE).
- Cada fila del listado HTML enlaza a `fichero_exposicion.jsp?id_archivo=N` con columnas **expediente** (p. ej. `5354/401`), **título** y a veces **ubicación** (distrito / vía).
- **Sesión JSESSIONID**: los listados devuelven HTML incompleto sin cookie de taboleiro; el adapter calienta sesión visitando `exposicion.jsp` antes de los listados.
- No hay API JSON; scrape determinista de tablas HTML (ISO-8859-1 / `latin-1`).
- `hoxe.vigo.org` concentra documentación del PGOM aprobado (modificaciones, planes especiales, gestión) pero es lento/inestable desde algunos entornos; el adapter prioriza el taboleiro activo de exposición.

## Licencias

- **No** hay tablón público de licencias concedidas (como Madrid DROUS).
- Los procedimientos **OB-*** (obra nueva, reforma, demolición, etc.) y **CP-*** (comunicación previa) están en el buscador de trámites (`q=obra`, `licencia obra`, …).
- El adapter ingiere filas **informativas** de trámite (URL `tramite.jsp?id_tramite=…`), no concesiones con fecha/distrito.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Portal `mapas.vigo.org` / ArcGIS Hub municipal; visor PGOM en `hoxe.vigo.org`; planeamiento autonómico SIOTUGA (`siotuga.xunta.gal`). Ninguno expone join estable **código expediente taboleiro → polígono** para scraping automático.
- **Estrategia:** Sin `_fetch_geometry`; el orquestador usa centroide municipal (`manifest` `centroid_lat/lon`) + jitter en `geocode`.
- **Limitaciones:** Taboleiro solo metadatos textuales; ficheros en exposición son ODT/PDF sin georreferencia enlazada.

## Limitaciones técnicas

- Codificación `latin-1` en sede.
- `fichero_exposicion` devuelve binario ODT embebido; no se parsea el documento.
- `hoxe.vigo.org` puede time-out fuera de la red local gallega.
