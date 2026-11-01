# Puerto Real — investigación portal ayuntamiento

**Municipio:** Puerto Real (Cádiz, Andalucía)  
**Slug:** `puerto-real`  
**INE:** 11032 · **BOJA:** sin entradas en cola (`bocm_count: 0`)

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web oficial | https://puertoreal.es | WordPress (tema 6tems), REST parcial |
| Urbanismo | https://puertoreal.es/atencion-a-la-ciudadania/servicios-municipales/urbanismo/ | Plantilla servicio; contenido cargado en cliente |
| PGOU aprobación definitiva | https://puertoreal.es/aprobacion-definitiva-pgou/ | ~80 PDFs del PGOU (memoria, planos, normas) |
| Ordenanzas urbanísticas (REST) | `GET /wp-json/wp/v2/ordenanzas?tipo_ordenanza=50` | 6 entradas (ámbitos planeamiento, modificaciones PGOU) |
| Noticias | https://puertoreal.es/atencion-a-la-ciudadania/noticias/ + sitemaps `noticia-sitemap*.xml` | CPT sin REST público; metadatos en Yoast JSON-LD |
| Sede electrónica | https://sede.eprinsa.es/puertoreal | Ember SPA (Eprinsa / Diputación Córdoba) |
| Tablón de edictos | https://sede.eprinsa.es/puertoreal/tablon-de-edictos | SPA sin API scrapeable |
| Trámites sede | https://sede.eprinsa.es/puertoreal/tramites | Catálogo SPA |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional |
| BOP Cádiz | https://bopcadiz.es/ | Boletín provincial |

**Nota:** `sede.puertoreal.es` y `transparencia.puertoreal.es` no resuelven desde el entorno cloud; la sede operativa es **eprinsa**.

## Cómo se listan expedientes / proyectos

1. **PGOU definitivo:** página única con enlaces directos a PDF en `/wp-content/uploads/2025/01/` (clasificación suelo, títulos normativos, estudios ambientales, planos).
2. **Ordenanzas tipo «Urbanísticas»:** entradas CPT `ordenanzas` (ámbitos Villanueva-Aldea Real, UE 7.1 Astilleros, sectorización Villanueva Norte, modificaciones puntuales PGOU). El cuerpo HTML no se expone en REST (`content.rendered` vacío).
3. **Noticias municipales:** URLs en sitemap; títulos y fechas vía schema.org `WebPage` (Yoast). Filtrado por palabras clave de planeamiento/obra en el slug.
4. **Sede eprinsa:** tablón y expedientes en SPA; no hay listado HTML/JSON público determinista (mismo patrón que Palma del Río, Fernán Núñez).

## Licencias de obra

- **No hay registro público estructurado** de licencias concedidas en la web municipal.
- La sede eprinsa ofrece trámites de licencia/comunicación previa sin histórico scrapeable.
- Algunas **noticias** mencionan licencias de obra a nivel informativo (prensa municipal).
- El adapter devuelve referencias al tablón, catálogo de trámites y página de urbanismo + noticias con keyword «licencia».

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - PGOU en PDF (planos @ 1:30000 / 1:2000) sin servicio WMS/WFS municipal.
  - SITUA / VITUA (Junta de Andalucía): instrumentos de planeamiento regional, sin join por expediente municipal.
  - Sede eprinsa: sin visor ArcGIS enlazado en HTML estático.
  - Agenda urbana municipal (noticia 2024): subdominio no accesible desde cloud en el momento de la investigación.
- **Estrategia:** centroide municipal en manifest (`36.5289, -6.1486`) + jitter del orquestador.
- **Limitaciones:** contenido urbanismo/noticias/ordenanzas renderizado en cliente; tablón sede solo SPA.

## Adapter

- `municipio.adapters.puerto_real:PuertoRealAyuntamientoAdapter`
- Proyectos: PDFs PGOU + ordenanzas REST + noticias (sitemap/Yoast) + enlace SITUA.
- Licencias: páginas informativas sede + noticias filtradas.
