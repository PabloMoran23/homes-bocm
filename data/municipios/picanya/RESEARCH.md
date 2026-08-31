# Picanya — investigación portal ayuntamiento

**Municipio:** Picanya (Valencia, Comunitat Valenciana)  
**Slug:** `picanya`  
**INE:** 46195  
**Boletín:** DOGV (`dogv`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.picanya.org | SPA Mithril (Digital Value) |
| Oficina virtual urbanismo | https://www.picanya.org/administracio/oficina-virtual/urbanisme | Enlaces a trámites UR.* en sede |
| Portal transparencia | https://transparencia.picanya.org | SPA Digital Value |
| Sede electrónica | https://picanya.sede.dival.es | **Operativa** — plataforma Dival/Sedipualba |
| Tablón de anuncios | https://picanya.sede.dival.es/tablondeanuncios/ | **Operativa** — HTML + RSS |
| Tablón RSS | https://picanya.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Feed RSS determinista (iso-8859-1) |
| Catálogo trámites | https://picanya.sede.dival.es/catalogoservicios.aspx | ~30 trámites UR.* urbanismo |
| API contenidos | https://api.digitalvalue.es/contents/picanya/collections/articulos | Noticias municipales (sin planeamiento) |

## Tablón de anuncios (Sedipualba / Dival)

- **CMS:** ASP.NET Sedipualba (`picanya.sede.dival.es`).
- **Listado:** RSS `tablon_rss.aspx` (~20 anuncios recientes) + HTML paginado con filtro por área (Urbanisme = id 776).
- **Documentos:** PDF en `tablondeanuncios/documento.aspx?id=…`.
- **Ficha anuncio:** `tablondeanuncios/anuncio.aspx?id=…`.

### Ejemplos urbanismo (ago 2026)

| Título | Tipo |
|--------|------|
| REPARCELACIÓN D4 VISTABELLA — rectificación expediente Sector D4 Vistabella | Reparcelación / plan parcial |
| EDICTE aprovació definitiva MC 2026-41 | Edicto modificación créditos (no urbanismo) |
| Anunci aprovació ordenança preu públic aparcament Sanchis Guarner | Ordenanza (indirecto) |

## Licencias de obra

- No hay dataset público de concesiones históricas.
- Catálogo sede con trámites UR.* en línea: licencia edificación (UR.003), DR obras (UR.098), parcelación (UR.009), etc.
- Licencias concedidas se publican como edictos en tablón cuando el ayuntamiento las anuncia (pocos en RSS actual).

## Planeamiento / expedientes

- **PGOU:** homologado 05/11/1998 (BOP 19/04/1999); sin visor municipal propio.
- **ICV GVA WFS:** capas `Planeamiento.Zonificacion` e `InventarioSuSuz` con geometría municipal.
- **Digital Value API:** noticias de obras públicas (rehabilitación sedes) pero no expedientes urbanísticos estructurados.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento`:
    - `Planeamiento.Zonificacion`: 1 polígono («MODIFICACIÓN ORDENACIÓN ESTRUCTURAL SECTOR OESTE PLAYA», exp. 20020869).
    - `InventarioSuSuz`: 6 polígonos (Industrial Piles Pueblo, Residencial Oeste Playa, Residencial Piles Pueblo, UE 1-3).
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion
  - Sin visor urbanístico municipal enlazado a expedientes del tablón.
- **Estrategia:** paginación WFS por `startIndex` (Zonificacion offsets 0–14000; InventarioSuSuz 0–4000 step 200), filtro cliente `cod_ine_mun=46195`; matching keyword en títulos tablón (vistabella, sector, reparcel).
- **Limitaciones:**
  - WFS sin CQL efectivo → paginación costosa (~30 s en CI).
  - Geometría por expediente del tablón no disponible directamente; matching por keywords.
  - Web SPA sin REST pública de planeamiento.

## Limitaciones generales

- Tablón RSS con ~20 anuncios; histórico limitado en feed.
- Mayoría de anuncios recientes son empleo público, no urbanismo.
- Transparencia SPA sin API pública documentada para documentos urbanísticos.
- PGOU de 1998; poca actividad de planeamiento reciente publicada en web.

## Adapter implementado

- `municipio.adapters.picanya:PicanyaAyuntamientoAdapter`
- Fuentes: tablón RSS Dival + trámites UR.* catálogo + seeds ICV GVA WFS + transparencia.
- IDs: `picanya-lic-*` / `picanya-proy-*` (sha256[:14]).
