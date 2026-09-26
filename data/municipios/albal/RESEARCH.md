# Albal — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `albal` |
| INE | 46007 |
| Provincia | Valencia |
| CCAA | Comunitat Valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://albal.es | WordPress (REST API restringida a usuarios autenticados) |
| Planeamiento | https://albal.es/es/areas-y-servicios-2/urbanismo-y-medio-ambiente/planeamiento-y-gestion/ | PGOU, modificaciones, sectores, UEs, planes de riesgo, PDFs/DOGV |
| Proyectos municipales | https://albal.es/es/areas-y-servicios-2/urbanismo-y-medio-ambiente/proyectos-municipales/ | Proyectos de obras públicas, planes locales |
| Sede electrónica | https://albal.sede.dival.es | Plataforma Dival (Sedipualba) |
| Tablón RSS | https://albal.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Edictos recientes (~16 items en feed) |
| Catálogo trámites | https://albal.sede.dival.es/catalogoservicios.aspx | URB004–URB026 (licencias obras, parcelación, DR, etc.) |

## Cómo se listan expedientes / proyectos

- **Planeamiento:** página WordPress estática con enlaces a PDFs (PGOU 2002, modificaciones 1–16, sectores 1.1.a/1.1.b/1.2/2.A, planes PAM/PTME, retasaciones). Sin API JSON pública.
- **Proyectos municipales:** enlaces a PDFs de proyectos de infraestructura (vestuarios, césped artificial, pistas deportivas, etc.).
- **Tablón sede:** RSS XML con título, fecha y enlace a `anuncio.aspx?id=`. Pocos anuncios urbanísticos recientes (mayoría personal/contratación).
- **Sin visor de expedientes** ni listado de concesiones de licencias publicadas.

## Cómo se publican licencias

- **No hay dataset ni tablón de licencias concedidas.** Las licencias se tramitan vía sede (declaración responsable URB004, licencia obras URB005, parcelación URB006, etc.) sin publicar resoluciones en listado abierto.
- El tablón publica edictos genéricos; la suspensión DANA (jun 2025) aparece en la web municipal.
- Estrategia adapter: páginas informativas de trámites sede + tablón RSS filtrado.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capas: `Planeamiento.Zonificacion` (~3 polígonos INE 46007) y `ms:InventarioSuSuz` (~24 polígonos)
  - Campo filtro: `cod_ine_mun=46007`; etiqueta en `denominaci`, expediente en `expediente`
- **Estrategia:** consulta WFS con paginación `startIndex`; matching por keywords (PGOU, sector, UE) en título del proyecto; merge de polígonos para PGOU.
- **Limitaciones:**
  - No hay visor ArcGIS municipal ni enlace expediente→geometría.
  - WFS solo cubre instrumentos de planeamiento (zonificación), no licencias individuales ni expedientes del tablón.
  - Sin geometría por anuncio/PDF.

## Limitaciones generales

- WordPress REST API bloqueada (401).
- Tablón RSS con pocos items urbanísticos.
- Licencias sin publicación de concesiones.
- SSL válido en sede y web.
