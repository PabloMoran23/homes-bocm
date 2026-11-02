# Almassora — investigación portal ayuntamiento

**Municipio:** Almassora (Castellón, Comunitat Valenciana)  
**INE:** 12008  
**Boletín:** sin entrada BOCM en cola (`Sin boletín asociado`)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.almassora.es |
| API DigitalValue | https://api.digitalvalue.es/almassora/collections/articulos |
| Sede (DigitalValue) | https://sede.almassora.es |
| Urbanismo | https://www.almassora.es/es/articulos/urbanismo |
| Tablón de anuncios | https://www.almassora.es/es/articulos/tablon-de-anuncios |
| Trámites | https://www.almassora.es/es/articulos/tramites |
| Planeamiento municipal | https://sede.almassora.es/es/articulos/planeamiento-municipal |
| PGOU (DOGV) | https://dogv.gva.es/portal/ficha_disposicion_pc.jsp?sig=003731/2020&L=1 |

## CMS y tecnología

- **ZityBuilder / DigitalValue** (Mithril.js + API REST `api.digitalvalue.es/almassora`).
- Artículos y noticias en colección `articulos` (~800+); páginas estáticas en rutas `/es/articulos/{slug}`.
- **Sede electrónica** en subdominio `sede.almassora.es` (misma stack, no sede espublico gestiona).
- `almassora.sedelectronica.es/board` responde 200 pero muestra selector “sede indeterminada” (no usable).

## Proyectos / planeamiento

### Fuentes

1. **ICV WFS** — sectores SU/SUZ y zonificación del planeamiento valenciano (`cod_ine_mun=12008`; >200 polígonos en inventario).
2. **API DigitalValue** — noticias de información pública, costas/deslinde, reuniones de urbanismo, etc. (filtro estricto anti-ruido).
3. **Hub web urbanismo** — PDFs en CDN (`cdn.digitalvalue.es/almassora/assets2/…`) y enlace DOGV PGOU.
4. **Páginas semilla** — urbanismo, planeamiento municipal, DOGV.

### Listado

- API paginada `limit`/`offset` sobre `articulos`.
- WFS: `GetFeature` GML3, `CQL_FILTER=cod_ine_mun='12008'`, paginación `STARTINDEX`.
- Documentos urbanísticos embebidos en HTML de `/es/articulos/urbanismo`.

## Licencias de obra

- **No hay registro público** de concesiones de licencias (solo trámites informativos).
- Tablón vía web municipal (noticias/anuncios); sin tabla estructurada tipo espublico `/board`.
- Fuentes del adapter: páginas informativas (tablón, trámites, formularios sede, urbanismo) + artículos API que mencionen licencias.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS ICV: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capas: `ms:InventarioSuSuz`, `Planeamiento.Zonificacion`
  - Campo municipio: `cod_ine_mun` = `12008`
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion`
- **Estrategia:** paginar WFS filtrado por INE, convertir `gml:Polygon` → GeoJSON EPSG:4326; match textual UE/sector en títulos de noticias.
- **Limitaciones:**
  - Geometría a nivel de sector/zonificación ICV, no de expedientes del tablón.
  - Sin visor ArcGIS municipal propio enlazado a expedientes.
  - Tablón sin coordenadas.

## Limitaciones generales

- Falsos positivos en noticias con “urbano/urbanismo” no planeamiento (filtrados en adapter).
- Subdominio espublico legacy no operativo para Almassora.
- Sync Supabase depende de `SUPABASE_DB_URL` en CI/agente.
