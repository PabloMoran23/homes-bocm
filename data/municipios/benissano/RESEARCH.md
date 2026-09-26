# Benissanó — investigación portal ayuntamiento

**Municipio:** Benissanó (Valencia, Comunitat Valenciana)  
**Slug:** `benissano`  
**INE:** 46069  
**Boletín:** DOGV (`dogv`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://ajuntamentbenissano.es | **Operativa** — WordPress 5.9 Bridge + WPML |
| Portal transparencia urbanismo | https://ajuntamentbenissano.es/es/portal-de-transparencia/urbanismo-y-obras-publicas/ | **Operativa** — PDFs NNSS/HHGG |
| Bandos municipales (RSS) | https://ajuntamentbenissano.es/es/feed/ | Feed WordPress con edictos urbanísticos |
| WP REST API | https://ajuntamentbenissano.es/es/wp-json/wp/v2/posts | JSON determinista |
| Sede electrónica | https://benissano.sede.dival.es | **Operativa** — plataforma Dival/Sedipualba |
| Tablón de anuncios | https://benissano.sede.dival.es/tablondeanuncios/ | **Vacío** (ago 2026) |
| Tablón RSS | https://benissano.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Sin anuncios |
| Catálogo trámites | https://benissano.sede.dival.es/catalogoservicios.aspx | Solo trámites genéricos |
| Dominio legacy | https://www.benissano.es | **Timeout** — no responde |
| Sede espublico | https://benissano.sedelectronica.es | **No operativa** — «Sede Electrónica Indeterminada» |

## Cómo se listan expedientes

### WordPress (web municipal)

- **CMS:** WordPress Bridge + Yoast SEO + WPML (valenciano/castellano).
- **Bandos y noticias:** posts en categorías `bando-municipal`, `noticias`, `actualidad`.
- **Listado:** REST API `wp-json/wp/v2/posts` (paginado, 100/página) y RSS `/es/feed/`.
- **Documentos:** PDFs enlazados en posts y en transparencia (`wp-content/uploads/` y subdominio `ayuntamientobenisano.es`).

### Transparencia (normas subsidiarias)

- Página estática con ~10 PDFs de normas subsidiarias, modificaciones BOP/DOGV y catálogo HHGG (2019).
- Sin API; scrape de enlaces `href="*.pdf"`.

### Sede Dival (tablón)

- **CMS:** ASP.NET Sedipualba en `benissano.sede.dival.es`.
- **Listado:** RSS `tablon_rss.aspx` (vacío en investigación).
- Sin expedientes urbanísticos publicados actualmente.

## Licencias de obra

- No hay dataset público de concesiones de licencia.
- Catálogo sede sin trámites de licencia urbanística en línea (solo registro, reclamaciones, empadronamiento).
- Una licencia de actividad (manipulación cebollas/patatas, 2019) publicada como noticia WP.
- Licencias futuras aparecerán en tablón Dival o bandos municipales.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes investigadas:**
  - ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento` capa `Planeamiento.Zonificacion` — **0 features** con `cod_ine_mun=46069` (paginación completa WFS GML/CSV).
  - Visor GVA general (`visor.gva.es`) sin capa municipal enlazada a expedientes del portal.
  - Web municipal: plano estático en `/es/municipio/plano/` (imagen, sin GeoJSON/WFS).
  - Transparencia y bandos: solo PDFs sin georreferenciación.
- **Estrategia:** sin fuente GIS pública; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Sin visor urbanístico ArcGIS/WFS municipal.
  - Documentación histórica solo en PDF.
  - Tablón sede vacío.

## Limitaciones generales

- `www.benissano.es` no responde (timeout); web activa en `ajuntamentbenissano.es`.
- Sede histórica `benissano.sedelectronica.es` no resuelve al ayuntamiento.
- Tablón Dival sin anuncios recientes.
- Sin licencias de obra mayor publicadas de forma sistemática.

## Adapter implementado

- `municipio.adapters.benissano:BenissanoAyuntamientoAdapter`
- Fuentes: WP REST API + transparencia PDFs + tablón RSS Dival (vacío) + páginas informativas trámites.
- IDs: `benissano-lic-*` / `benissano-proy-*` (sha256[:14]).
