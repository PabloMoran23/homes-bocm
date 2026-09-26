# Investigación portal — Valdaracete, Brea de Tajo y Estremera

**Slug:** `valdaracete-brea-de-tajo-y-estremera`  
**Nota:** Entrada de cola generada por un anuncio BOCM que menciona tres municipios. **Estremera** ya tiene adapter propio (`estremera`, PR previa). Este onboarding cubre **Valdaracete** y **Brea de Tajo**.

## URLs base y páginas semilla

### Valdaracete

| Recurso | URL | Notas |
|---------|-----|-------|
| Web municipal (Joomla JA University) | https://www.valdaracete.org | Accesible |
| Vivienda / licencias | https://www.valdaracete.org/index.php/vivienda | PDFs obra mayor/menor, primera ocupación, instancia |
| Normativa municipal | https://www.valdaracete.org/index.php/normativa-municipal | Ordenanza licencias urbanísticas (ord1.pdf) |
| Sede eAdmin (Maggioli) | https://sedevaldaracete.eadministracion.es | SPA tablón sin filas scrapeables vía HTTP |
| Transparencia eAdmin | https://transparenciavaldaracete.eadministracion.es | Sin urbanismo indexado scrapeable |

### Brea de Tajo

| Recurso | URL | Notas |
|---------|-----|-------|
| Web municipal (WordPress) | https://breadetajo.es | Accesible |
| Categoría urbanismo | https://breadetajo.es/category/urbanismo/ | Pocas entradas; obras municipales |
| Impresos licencias | https://www.breadetajo.es/pdf/solicitud_licencia_urbanistica.pdf | + declaración responsable, instancia |
| Sede eAdmin | https://sedebreadetajo.eadministracion.es | Maggioli SPA |
| Transparencia | https://transparenciabreadetajo.eadministracion.es | |

### Estremera (referencia, no re-scrapeado aquí)

| Recurso | URL |
|---------|-----|
| Adapter existente | `municipio/adapters/estremera.py` |
| Web | https://estremera.es |

## Cómo se listan expedientes

- **Valdaracete:** Sin visor ni listado HTML de expedientes urbanísticos. Licencias vía formularios PDF en `/vivienda`. Noticias Joomla desactualizadas (contenido mezclado con otros municipios).
- **Brea de Tajo:** WordPress REST (`/wp-json/wp/v2/posts`) con filtro regex urbanismo. Sin tablón scrapeable en sede eAdmin.
- **Planeamiento:** Ámbitos publicados en **SITCM** (Comunidad de Madrid), no en webs municipales.

## Licencias

- Formularios PDF en web Valdaracete (obra mayor/menor, primera ocupación, instancia general).
- Formularios PDF Brea de Tajo (solicitud licencia, declaración responsable, instancia).
- Sedes eAdmin Maggioli para presentación electrónica (sin listado público scrapeable).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS SITCM `sitcm:VPLA_V_AMBITO` en `https://idem.comunidad.madrid/geoserver3/ows`
  - Valdaracete: `CQL_FILTER=DS_MUNICIPIO='VALDARACETE'` — ámbitos SAU, UE-1, UE-10, UE-2, UE-3 (5 polígonos)
  - Brea de Tajo: `CQL_FILTER=DS_MUNICIPIO='BREA DE TAJO'` — ámbitos UA-1 … UA-7 (7 polígonos)
- **Estrategia:** `GetFeature` GeoJSON `EPSG:4326`; proyectos SITCM con `geom_geojson` + centroide
- **Limitaciones:** Sin visor municipal enlazado a expediente; licencias sin georreferencia; sede SPA no scrapeable

## Limitaciones

- Slug compuesto: entradas duplicadas en cola (`valdaracete`, `brea-de-tajo`) pendientes de reconciliar.
- Valdaracete.org mezcla contenido legacy (OpenCMS URLs en PDFs).
- Brea de Tajo WP urbanismo con pocas noticias de planeamiento (más obras municipales).
- Sin `SUPABASE_DB_URL` en agente → sync omitido en CI.
