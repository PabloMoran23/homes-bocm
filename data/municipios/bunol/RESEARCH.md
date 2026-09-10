# Buñol — investigación portal ayuntamiento

**Municipio:** Buñol (Valencia, Comunitat Valenciana)  
**Slug:** `bunol`  
**INE:** 46077  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.bunyol.es | **Inaccesible** desde cloud agent (timeout TLS ~15 s) |
| Urbanismo | https://www.bunyol.es/pagina/urbanismo-0 | Drupal — M14 Normas Subsidiarias, documentos PDF |
| Sede electrónica | https://bunyol.sede.dival.es | **Operativa** — plataforma Dival/Sedipualba (ASP.NET) |
| Tablón de anuncios | https://bunyol.sede.dival.es/tablondeanuncios/ | **Operativa** — RSS + anuncios |
| Tablón RSS | https://bunyol.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Feed RSS determinista |
| Catálogo trámites | https://bunyol.sede.dival.es/catalogoservicios.aspx | Trámites genéricos (registro, reclamaciones) |
| Cita previa | https://citaprevia.xn--buol-hqa.es | Citas con técnicos municipales |

## Tablón de anuncios (Sedipualba / Dival)

- **CMS:** ASP.NET Sedipualba (`bunyol.sede.dival.es`).
- **Listado:** RSS `tablon_rss.aspx` con título, enlace `anuncio.aspx?id=` y fecha.
- **Área Urbanismo:** filtro `area=709` (Urbanismo y Medio Ambiente).
- **Documentos:** PDF en `tablondeanuncios/documento.aspx?id=…&modo=guardar`.
- **Paginación:** ~20 anuncios en RSS (ago–sep 2026); histórico limitado en feed.

### Ejemplos urbanismo (tablón / RSS)

| Título | Tipo |
|--------|------|
| Exposición pública proyecto Planta Solar Fotovoltaica Buñol I | Información pública / energía |
| anuncio aprobación inicial modificación tasa publicación | Tasa (no urbanismo) |
| ANUNCIO-Aprobación definitiva Ordenanza Convivencia Ciudadana | Ordenanza (no urbanismo) |

## Planeamiento municipal

- **Instrumento vigente:** Normas Subsidiarias de Planeamiento (exp. 19870019).
- **Texto Consolidado:** entregado en 2023 (AUG-ARQUITECTOS).
- **En tramitación:** Modificación M13 (estructural, aprobación autonómica) y M14 (pormenorizada, municipal).
- Documentación publicada en web `/pagina/urbanismo-0` (Drupal).

## Licencias de obra

- No hay dataset público de concesiones de licencia.
- Catálogo sede sin trámites de licencia urbanística en línea.
- Licencias publicadas aparecen como edictos en tablón cuando el ayuntamiento los anuncia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento` capa `Planeamiento.Zonificacion`, filtro cliente `cod_ine_mun=46077` (CQL_FILTER del servidor no funciona).
  - 3 polígonos de zonificación; denominación: «Normas subsidiarias» (exp. 19870019).
  - Sin visor urbanístico municipal enlazado a expedientes del tablón.
- **Estrategia:** muestreo WFS por `startIndex` (offsets 0–13500), merge polígonos por keyword en título (normas subsidiarias, modificaci, solar).
- **Limitaciones:**
  - WFS sin filtro CQL efectivo → paginación costosa (~90 s).
  - Geometría por expediente del tablón no disponible; solo matching por keywords de planeamiento.
  - Web www.bunyol.es no accesible desde entorno cloud (timeout); sede Dival operativa.

## Limitaciones generales

- Web oficial con timeout desde agentes cloud; sede Dival es la fuente principal.
- Tablón con pocos anuncios urbanísticos recientes en RSS.
- Sin licencias de obra explícitas en feed actual; páginas informativas de trámites como fallback.

## Adapter implementado

- `municipio.adapters.bunol:BunolAyuntamientoAdapter`
- Fuentes: tablón RSS Dival + seeds ICV GVA WFS + páginas informativas trámites.
- IDs: `bunol-lic-*` / `bunol-proy-*` (sha256[:14]).
