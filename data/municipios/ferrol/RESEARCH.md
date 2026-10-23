# Ferrol — portal ayuntamiento

## Fuentes base

| Recurso | URL |
|---------|-----|
| Web / sede municipal | https://www.ferrol.gal (alias https://www.ferrol.es) |
| Planeamiento urbanístico (tabla pública) | https://www.ferrol.gal/Sede/PlaneamentoUrbanistico |
| Detalle expediente planeamiento | `/Sede/PlaneamentoUrbanisticoAmpliar/{id}` |
| Catálogo trámites sede (Urbanismo) | https://www.ferrol.gal/Sede/Tramites |
| Detalle trámite | `/Sede/TramitesAmpliar/{id}` |
| Sede Cividas (JSF, trámites telemáticos) | https://www.ferrol.gal:8443/cividas-core-web-ferrol/ |
| Cartografía digital / SIX municipal | https://www.ferrol.gal/Sede (sección «Cartografía dixital») |
| Visor ABS mapas (legacy) | http://www.ferrol.es/absatlas/absmapas/ui/loc/ctrl_avanzado.aspx |
| Inventario SIOTUGA (Xunta, INE **15036**) | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15036&lang=es_ES |
| PXOM histórico (metadatos Xeocatálogo) | https://xeocatalogo.xunta.gal/xeocatalogo/srv/api/records/GLG_SIOTUGA_PXOM_ferrol_20001228 |

## Proyectos / expedientes

- El ayuntamiento publica una **tabla HTML** (DataTables) en `Sede/PlaneamentoUrbanistico` con fecha, figura, título, enlaces BOP/DOG y ficha «Ampliar».
- Complemento: **inventario autonómico SIOTUGA** (`query_document.php`, clases 13 desarrollo + 14 plan xeral) con documentos aprobados y figuras (sectorización, PGOM, etc.).
- No hay API JSON pública en el portal municipal; scrape determinista de tablas + POST SIOTUGA con token de sesión.
- Desde entornos cloud el dominio `ferrol.gal` / `ferrol.es` suele **no responder** (timeout); el adapter usa **fallback archive.org** (`wayback_fallback`) y SIOTUGA (accesible).

## Licencias

- **No** hay tablón público de licencias concedidas con dirección/fecha.
- Procedimientos urbanísticos listados en `Sede/Tramites` (licencia urbanística, CP-05 obras menores, primera ocupación, etc.) — filas **informativas** de trámite, no concesiones.
- Tramitación telemática vía sede Cividas (PrimeFaces); sin listado scrapeable de resoluciones.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** SIOTUGA ofrece **WMS** del PXOM municipal; cartografía municipal SIX/AbsAtlas y visor SIOTUGA (`siotuga.xunta.gal/siotuga/carto`) muestran instrumentos de planeamiento, pero **sin join estable** código expediente municipal / fila SIOTUGA → polígono descargable por API.
- **Estrategia:** Metadatos de proyectos desde tablón municipal + SIOTUGA; coordenadas vía centroide municipal en `manifest` + jitter en `geocode`.
- **Limitaciones:** Portal municipal inaccesible fuera de Galicia en muchos entornos; geometría de ámbito solo en PDFs/planos del expediente, no enlazada al listado.

## Limitaciones técnicas

- Timeout / bloqueo de red a `www.ferrol.gal` y `www.ferrol.es` desde cloud agents → `wayback_fallback` + `prefer_wayback` opcional.
- Sede `:8443` requiere TLS; puede necesitar `sede_insecure_ssl` en redes restrictivas.
- Tabla planeamiento puede crecer; el parser recorre todas las filas con enlace `PlaneamentoUrbanisticoAmpliar`.
