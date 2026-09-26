# Alberic — investigación portal ayuntamiento

**Municipio:** Alberic (Valencia, Comunitat Valenciana)  
**Slug:** `alberic`  
**INE:** 46005  
**Boletín:** DOGV (`dogv`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial (Drupal) | https://www.alberic.es | **Operativa** con User-Agent Mozilla (502/500 con UA genérico en CI) |
| Urbanismo | https://www.alberic.es/es/pagina/urbanismo | Sección hub |
| Sección urbanismo | https://www.alberic.es/es/seccion/urbanismo | Listado documentos y enlaces |
| PGOU | https://www.alberic.es/es/pagina/plan-general-ordenacion-urbana | ~40+ PDFs cartografía y normas |
| Planeamiento general | https://www.alberic.es/es/pagina/planeamiento-general-12 | Planes parciales (sectores I-1/I-2/I-3, residencial R) |
| Gestión urbanística | https://www.alberic.es/es/pagina/gestion-urbanistica | Programación sectorial, UE |
| Licencias / DR | https://www.alberic.es/es/pagina/tramitaciones-licencias-declaraciones-responsables | Formularios PDF |
| Portal transparencia | https://transparencia.alberic.es | DigitalValue / Zity |
| Planeamiento transparencia | https://transparencia.alberic.es/es/transparencia/planejament-urbanistic | Enlaces ICV + visor GVA |
| API transparencia | https://api.digitalvalue.es/alberic/collections/articulos | JSON artículos + ficheros |
| Sede electrónica | https://alberic.sede.dival.es | **Operativa** — Dival/Sedipualba (ASP.NET) |
| Tablón de anuncios | https://alberic.sede.dival.es/tablondeanuncios/ | RSS + anuncios |
| Tablón RSS | https://alberic.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Feed determinista |
| Catálogo trámites | https://alberic.sede.dival.es/catalogoservicios.aspx | Instancia general, sin licencias en línea |

## Cómo se listan expedientes / planeamiento

- **Web Drupal:** páginas estáticas con enlaces a PDF en `/sites/www.alberic.es/files/*.pdf`. Secciones: PGOU, planes parciales (industrial I-1/I-2/I-3, residencial R), gestión urbanística (programación sector I-3, San Cristóbal), auditoría Monte Júcar.
- **Transparencia DigitalValue:** árbol de nodos bajo «Información urbanística» (programas de actuación, sector I-3, ERP delimitación). Ficheros en `cdn.digitalvalue.es/alberic/assets2/{id}`.
- **Tablón Dival:** RSS con `anuncio.aspx?id=`; documentos PDF en `documento.aspx?id=`. Pocos anuncios urbanísticos recientes (ej. modificación proyecto I-3, ago 2026).
- **Sin** listado público de expedientes urbanísticos individuales con código (consulta requiere sede/autenticación).

## Licencias de obra

- No hay dataset público de concesiones de licencia.
- Formularios en web (`tramitaciones-licencias-declaraciones-responsables`) y trámites presenciales/sede.
- Edictos de licencia aparecen en tablón cuando se publican (histórico limitado en RSS actual).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento` capa `Planeamiento.Zonificacion`, filtro cliente `cod_ine_mun=46005` (CQL_FILTER del servidor no funciona).
  - 3 polígonos: «Plan general» (exp. 20130190), «Plan parcial sector VI industrial», «Plan parcial sector VII industrial» (encontrados con `startIndex=2000`).
  - Enlaces en transparencia a ICV (`icv.gva.es`) y visor GVA (`visor.gva.es`).
  - Sin visor municipal enlazado a expedientes del tablón.
- **Estrategia:** paginación WFS por `startIndex` (offsets 0–14000); merge polígonos por keywords en título (plan general, sector VI/VII, industrial); enriquecimiento en filas ICV y matching en PDFs web.
- **Limitaciones:**
  - WFS sin filtro CQL efectivo → paginación costosa (~25 s).
  - Geometría por expediente de licencia no disponible.
  - Web corporativa inestable sin User-Agent Mozilla en algunos entornos.

## Limitaciones generales

- Catálogo sede sin trámites urbanísticos específicos en línea (solo instancia general).
- Tablón RSS con pocos anuncios y mayoría administrativos/no urbanísticos.
- PDFs web sin metadatos estructurados (título inferido del nombre de fichero).

## Adapter implementado

- `municipio.adapters.alberic:AlbericAyuntamientoAdapter`
- Fuentes: crawl web Drupal (PDFs + páginas semilla) + transparencia DigitalValue + tablón RSS Dival + ICV GVA WFS.
- IDs: `alberic-lic-*` / `alberic-proy-*` (sha256[:14]).
