# Canals — investigación portal ayuntamiento

**Municipio:** Canals (Valencia, Comunitat Valenciana)  
**Slug:** `canals`  
**INE:** 46068  
**Boletín:** DOGV (`dogv`, 3 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial (nueva) | https://www.canals.es | SPA proxy a subdominios |
| Web corporativa Liferay | https://web.canals.es | **Operativa** — Liferay 6.2 |
| Urbanisme i habitatge | https://web.canals.es/serveis-municipals/urbanisme-i-habitatge | Sección servicios (contenido mínimo) |
| Portal transparencia | https://transparencia.canals.es | Liferay transparencia (noticias institucionales) |
| Sede electrónica | https://canals.sede.dival.es | **Operativa** — plataforma Dival/Sedipualba (ASP.NET) |
| Tablón de anuncios | https://canals.sede.dival.es/tablondeanuncios/ | **Operativa** — RSS + anuncios |
| Tablón RSS | https://canals.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Feed RSS determinista |
| Catálogo trámites | https://canals.sede.dival.es/catalogoservicios.aspx | Solo trámites genéricos (registro, reclamaciones) |
| Sede espublico | https://canals.sedelectronica.es | **No operativa** — «Sede Electrónica Indeterminada» |

## Tablón de anuncios (Sedipualba / Dival)

- **CMS:** ASP.NET Sedipualba (`canals.sede.dival.es`), no espublico gestiona.
- **Listado:** RSS `tablon_rss.aspx` con título, enlace `anuncio.aspx?id=` y fecha.
- **Documentos:** PDF en `tablondeanuncios/documento.aspx?id=…&modo=guardar`.
- **Paginación:** ~4 anuncios visibles en RSS (ago 2026); histórico limitado en feed.

### Ejemplos (ago 2026)

| Título | Tipo |
|--------|------|
| 06 07 Edicto aprob. inicial ordenanza tràfic | Ordenanza (urbanismo indirecto) |
| 21 01 Edicto BOP aprobación provisional | Edicto / aprobación |
| 13 01 Edicto | Edicto genérico |

## Licencias de obra

- No hay dataset público de concesiones de licencia.
- Catálogo sede sin trámites de licencia urbanística en línea.
- Licencias publicadas aparecen como edictos en tablón cuando el ayuntamiento los anuncia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento` capa `Planeamiento.Zonificacion`, filtro cliente `cod_ine_mun=46068` (CQL_FILTER del servidor no funciona).
  - ~39 polígonos de zonificación; denominaciones: «Plan general» (exp. 19960235), «MOD. PG área Industrial Les Moles».
  - DipCAS OpenData (`cod_mun=46068`): sin registros.
  - Sin visor urbanístico municipal enlazado a expedientes del tablón.
- **Estrategia:** muestreo WFS por `startIndex` (offsets 0, 2000, 4000, 6000, 10500, 13500), merge polígonos por keyword en título (plan general, moles, ordenanza).
- **Limitaciones:**
  - WFS sin filtro CQL efectivo → paginación costosa (~22 s).
  - Geometría por expediente del tablón no disponible; solo matching por keywords de planeamiento.
  - Web urbanisme Liferay sin PDFs ni visor embebido.

## Limitaciones generales

- Sede histórica `canals.sedelectronica.es` no resuelve al ayuntamiento.
- Web nueva `canals.es` no indexa urbanismo; contenido en Liferay legacy.
- Tablón con pocos anuncios recientes; sin licencias de obra explícitas en RSS actual.
- Transparencia Liferay sin sección urbanismo accesible por URL directa.

## Adapter implementado

- `municipio.adapters.canals:CanalsAyuntamientoAdapter`
- Fuentes: tablón RSS Dival + seeds ICV GVA WFS + páginas informativas trámites.
- IDs: `canals-lic-*` / `canals-proy-*` (sha256[:14]).
