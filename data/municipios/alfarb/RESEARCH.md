# Alfarb — investigación portal ayuntamiento

**Municipio:** Alfarb (Valencia, Comunitat Valenciana)  
**Slug:** `alfarb`  
**INE:** 46026  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://alfarb.es | **Captcha SiteGround** — bloquea scraper automatizado |
| Normes Subsidiàries | https://alfarb.es/normes-subsidiaries/ | Contenido documentado (plànols zonificació) — captcha en fetch |
| Sede electrónica | https://alfarb.sede.dival.es | **Operativa** — plataforma Dival/Sedipualba (ASP.NET) |
| Tablón de anuncios | https://alfarb.sede.dival.es/tablondeanuncios/ | **Operativa** — RSS + anuncios |
| Tablón RSS | https://alfarb.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Feed RSS determinista |
| Catálogo trámites | https://alfarb.sede.dival.es/catalogoservicios.aspx | Trámites genéricos + ocupación vía pública/obra |
| Sede GVA | https://alfarb.sede.gva.es | **503** Service Unavailable |
| Sede espublico | https://alfarb.sedelectronica.es | **No operativa** — «Sede Electrónica Indeterminada» |

## Tablón de anuncios (Sedipualba / Dival)

- **CMS:** ASP.NET Sedipualba (`alfarb.sede.dival.es`).
- **Listado:** RSS `tablon_rss.aspx` con título, enlace `anuncio.aspx?id=` y fecha.
- **Documentos:** PDF en `tablondeanuncios/documento.aspx?id=…`.
- **Contenido actual (sep 2026):** anuncios administrativos (jurado, premios valenciano, IAE, SEPE) — sin edictos urbanísticos recientes.

## Licencias de obra

- No hay dataset público de concesiones de licencia urbanística.
- Catálogo sede incluye trámites de **ocupación vía pública con material de obra** (idtramite 18848–18852) pero no licencia de obra mayor/menor en línea.
- Licencias publicadas aparecerían como edictos en tablón cuando el ayuntamiento las anuncie.

## Normes Subsidiàries (web municipal)

Documentación de planeamiento publicada en WordPress (`alfarb.es/normes-subsidiaries/`):

- Classificació del sòl — estructura general i orgànica del territori
- Zonificació: Casc Urbà, El Puntal, Almaguer, Los Lagos
- Alineacions i rasantes por núcleos
- Infraestructures (xarxa aigua, enllumenat)

**Limitación:** SiteGround captcha (`sg-captcha`) impide scrape HTTP directo; seeds documentados con URL estática.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento` capa `Planeamiento.Zonificacion`, filtro cliente `cod_ine_mun=46026`.
  - 3 polígonos: «Normas subsidiarias», «HOMO PP SUELO INDUSTRIAL».
  - Capa `ms:InventarioSuSuz`: mismos 3 registros para Alfarb.
  - Sin visor urbanístico municipal propio.
- **Estrategia:** muestreo WFS por `startIndex` (offsets 0, 2000, 4000, 6000, 10500, 13500), merge polígonos por keyword en título (normas subsidiarias, suelo industrial, zonificación).
- **Limitaciones:**
  - WFS sin filtro CQL efectivo → paginación costosa (~90 s).
  - Geometría por expediente del tablón no disponible.
  - Web municipal con captcha; no se pueden extraer PDFs de normes automáticamente.

## Limitaciones generales

- `alfarb.es` protegido con captcha SiteGround.
- Sede histórica `alfarb.sedelectronica.es` no resuelve al ayuntamiento.
- Tablón sin anuncios urbanísticos recientes en RSS.
- Sin licencias de obra publicadas en dataset abierto.

## Adapter implementado

- `municipio.adapters.alfarb:AlfarbAyuntamientoAdapter`
- Fuentes: tablón RSS Dival + seeds ICV GVA WFS + normes subsidiàries (estáticas) + trámites obra vía pública.
- IDs: `alfarb-lic-*` / `alfarb-proy-*` (sha256[:14]).
