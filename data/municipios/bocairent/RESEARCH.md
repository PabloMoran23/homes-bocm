# Bocairent — investigación portal ayuntamiento

**Municipio:** Bocairent (Valencia, Comunitat Valenciana)  
**Slug:** `bocairent`  
**INE:** 46072  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.bocairent.es | **Operativa** — Drupal 9/10 Digital Value (ca/val) |
| Punto información catastral / Urbanismo | https://www.bocairent.es/es/pagina/catastro | Sección urbanismo (icono cadastre) |
| Impresos urbanismo | https://www.bocairent.es/es/pagina/descargar-impresos | **Operativa** — formularios PDF licencias |
| Portal transparencia | https://www.bocairent.es/es/pagina/portal-transparencia | Enlace a registro autonómico planeamiento GVA |
| Sede electrónica | https://bocairent.sede.dival.es | **Operativa** — plataforma Dival/Sedipualba (ASP.NET) |
| Tablón de anuncios | https://bocairent.sede.dival.es/tablondeanuncios/default.aspx | **Operativa** |
| Tablón RSS | https://bocairent.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Feed RSS determinista |
| Catálogo trámites | https://bocairent.sede.dival.es/catalogoservicios.aspx | Solo trámites genéricos (registro, padrón, reclamaciones) |

## Tablón de anuncios (Sedipualba / Dival)

- **CMS:** ASP.NET Sedipualba (`bocairent.sede.dival.es`).
- **Listado:** RSS `tablon_rss.aspx` con título, enlace `anuncio.aspx?id=` y fecha.
- **Documentos:** PDF en `tablondeanuncios/documento.aspx?id=…&modo=guardar`.
- **Paginación:** ~8 anuncios en RSS (sep 2026); histórico limitado en feed.

### Ejemplos (sep 2026)

| Título | Tipo |
|--------|------|
| Obertura informació pública PAI ampliació sol urbà tipus A i designació agent urbanitzador | PAI / información pública |
| Aprobación inicial modificación presupuestaria | No urbanismo (filtrado) |

## Licencias de obra

- No hay dataset público de concesiones de licencia.
- Catálogo sede sin trámites de licencia urbanística en línea (solo registro, padrón, reclamaciones).
- **Impresos descargables** en web municipal: obra mayor/menor, ambiental, ocupación, vado, apertura actividad, compatibilidad urbanística.
- Licencias publicadas aparecen como edictos en tablón cuando el ayuntamiento las anuncia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento`:
    - Capa `Planeamiento.Zonificacion` — 4 polígonos (Plan general exp. 19910182, normas subsidiarias Parc Natural Serra Mariola).
    - Capa `InventarioSuSuz` — 14 polígonos (sectores SU/SUZ: LOS OLMOS industrial, etc.).
  - Filtro cliente `cod_ine_mun=46072` (CQL_FILTER del servidor no funciona).
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion
- **Estrategia:** muestreo WFS por `startIndex` (offsets 0–18000), geometría embebida en seeds ICV; matching por keywords en títulos del tablón (PAI, sol urbà, plan general).
- **Limitaciones:**
  - WFS sin filtro CQL efectivo → paginación costosa (~2,5 min en backfill).
  - Geometría por expediente del tablón no enlazada directamente; solo matching heurístico.
  - Sin visor urbanístico municipal propio; web Drupal sin mapa interactivo de expedientes.

## Limitaciones generales

- Tablón RSS con pocos anuncios recientes; la mayoría no son urbanismo.
- Sin registro público de licencias concedidas (solo formularios e impresos).
- Portal transparencia enlaza al registro autonómico GVA, no a expedientes locales indexables.

## Adapter implementado

- `municipio.adapters.bocairent:BocairentAyuntamientoAdapter`
- Fuentes: tablón RSS Dival + seeds ICV GVA WFS (Zonificacion + InventarioSuSuz) + impresos/formularios web.
- IDs: `bocairent-lic-*` / `bocairent-proy-*` (sha256[:14]).
