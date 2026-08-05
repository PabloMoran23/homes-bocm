# Berzosa del Lozoya — investigación portal ayuntamiento

**Municipio:** Berzosa del Lozoya (`berzosa-del-lozoya`)  
**Comunidad:** Comunidad de Madrid  
**BOCM:** 11 entradas históricas (`bocm`)

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web municipal | https://www.berzosadelozoya.com | WordPress (Astra), gestión comarcadelajara |
| Descarga documentos | https://www.berzosadelozoya.com/ayuntamiento/descarga-de-documentos/ | Formularios licencias/DR urbanísticas (PDF) |
| Sede electrónica | https://sedeberzosadellozoya.eadministracion.es | eAdmin Maggioli (Angular SPA) |
| Tablón anuncios | https://sedeberzosadellozoya.eadministracion.es/PortalCiudadano/Tablon/wfrTablon.aspx | Redirige a SPA (sin HTML scrapeable) |
| Transparencia | https://transparenciaberzosadellozoya.eadministracion.es/portal | Portal eAdmin Maggioli |
| WP REST API | https://www.berzosadelozoya.com/wp-json/wp/v2/ | Páginas, posts, media |

## Cómo se listan expedientes / planeamiento

- **No hay sección de urbanismo ni visor de planeamiento** en la web municipal.
- **No hay listado público de expedientes** en HTML accesible; la sede eAdmin es una SPA Angular que carga datos vía API interna (no expuesta sin autenticación/reverse engineering).
- **Normativa urbanística** publicada como PDFs en la biblioteca de medios WP (ordenanzas fiscales y de servicios urbanísticos, limpieza de solares, residuos de construcción).
- **Formularios de trámites** (licencia obra mayor, actividad, comunicación previa, declaración responsable) en `/ayuntamiento/descarga-de-documentos/`.
- **BOCM:** 11 menciones históricas en el boletín regional; no hay re-parse en este adapter.

## Cómo se publican licencias

- **No hay dataset ni tablón scrapeable** de licencias concedidas.
- Solo **formularios informativos** (PDF) para solicitar licencias/DR en la web.
- La sede eAdmin permite presentar trámites electrónicamente pero no expone listado de concesiones.
- El adapter devuelve páginas de trámite + formularios como filas informativas (patrón Pozuelo/Robledo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes consultadas:**
  - SITCM WFS `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='BERZOSA DEL LOZOYA'` → **0 features**
  - No hay visor urbanístico, ArcGIS ni datos abiertos georreferenciados en el portal municipal.
  - Comunidad de Madrid IDEM: sin instrumentos de planeamiento digitalizados para este municipio rural del Valle del Lozoya.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [40.9757802, -3.5236736]`).
- **Limitaciones:** municipio pequeño (~257 hab.) sin PGOU digitalizado en SITCM; expedientes solo en sede interna.

## Limitaciones del scrape

- Sede eAdmin Maggioli: SPA Angular, tablón y trámites requieren JS; no hay API pública documentada.
- `berzosadelozoya.es` devuelve HTTP 500; dominio activo es `berzosadelozoya.com`.
- SSL de sede eAdmin: cadena CA no verificada → `insecure_ssl: true`.
- Sin licencias concedidas publicadas; solo trámites informativos.

## Adapter implementado

- **Módulo:** `municipio/adapters/berzosa_del_lozoya.py`
- **Fuentes:** WP descarga documentos + WP media API (ordenanzas urbanísticas) + páginas informativas sede/transparencia.
- **Geometría:** no implementada (`geometry_status: unavailable`).
