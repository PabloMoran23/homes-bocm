# Paterna — investigación portal ayuntamiento

Municipio: **Paterna** (`paterna`) — Huerta de Valencia, Comunitat Valenciana (DOGV).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica | https://sede.paterna.es/opensiac/main | OpenSIAC (GADD) |
| Tablón edictos | https://sede.paterna.es/opensiac/informacionpublica/infopublica.action?edictos=1 | Índice por grupos (PGOU, licencias ambientales, expropiaciones) |
| Búsqueda AJAX | POST `…/infopublica_search.action` | `botonTodos` / `descripcionPublicacion` |
| Catálogo trámites | https://sede.paterna.es/opensiac/informacionpublica/tramites_enter.action | Urbanismo / licencias |
| Licencias obra | https://sede.paterna.es/opensiac/informacionpublica/tramitesinfo?tramitesInfoForm.id=324 | DR / licencia urbanística |
| Licencias usos | https://sede.paterna.es/opensiac/informacionpublica/tramitesinfo?tramitesInfoForm.id=293 | Cambios de uso |
| Web institucional | https://www.paterna.es/ | Drupal; **timeout SSL** frecuente desde CI |
| Visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Zonificación CV |
| ICV WFS | https://terramapas.icv.gva.es/0702_Planeamiento | `ms:InventarioSuSuz`, `Planeamiento.Zonificacion` |

## Cómo se listan expedientes

- **CMS:** OpenSIAC (Java/Struts), codificación `iso-8859-15`.
- **Tablón:** tablas HTML en `infopublica.action?edictos=1` y búsqueda POST a `infopublica_search.action` → enlace `infopublica_ver.action?id=…`.
- **Detalle:** campos `Etiqueta` / `Descripcion` y PDFs `infopublica_descargar.action`.
- **Planeamiento:** modificaciones puntuales PGOU, PRI, expropiaciones y PUAM publicados en edictos (grupos «Patrimonio municipal», «Otros», etc.).
- **Handicap CI:** handshake TLS a `sede.paterna.es` puede exceder timeout desde cloud agents; el adapter tolera fallo y sigue con ICV WFS.

## Cómo se publican licencias

- Trámites informativos OpenSIAC (obra id=324, usos id=293); resoluciones puntuales en tablón (p. ej. licencias ambientales).
- No hay dataset ni API de licencias urbanísticas concedidas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** ICV WFS `InventarioSuSuz` / `Zonificacion` (`cod_ine_mun=46190`, INE 46190); visor GVA `spaicv0702_plan_zonificacion`.
- **Estrategia:** paginar WFS (STARTINDEX hasta ~14000; polígonos del municipio aparecen en offset ~8000+) y filtrar por `cod_ine_mun`; cruce por título/sector con edictos del tablón cuando la sede responde.
- **Limitaciones:** CQL_FILTER del servicio no filtra correctamente; tablón/PDF sin coords; sede con SSL lento desde CI; web `www.paterna.es` no scrapeable de forma fiable.

## Publicaciones urbanísticas (muestra tablón, 2026)

| Título (extracto) | Fecha |
|-------------------|-------|
| Modificación Puntual n.º 88 PGOU — info pública | 14/09/2026 |
| Modificación Puntual n.º 91 PGOU — aprobación definitiva | 01/09/2026 |
| Modificación Puntual n.º 90 (EGM ASIVALCO) | 26/05/2026 |
| Licencia ambiental — paneles solares C/ Fuster | 17/07/2026 |

## Limitaciones

- SSL lento/timeout hacia `sede.paterna.es` en entornos cloud (documentado).
- WFS ICV requiere barrido amplio de páginas para localizar features de Paterna.
- Sin registro histórico de licencias de obra en portal abierto.
