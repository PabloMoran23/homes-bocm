# Madarcos — investigación portal ayuntamiento

**Municipio:** Madarcos (`madarcos`)  
**Comunidad:** Comunidad de Madrid (Sierra del Rincón)  
**BOCM:** 4 entradas históricas (`bocm`)

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web municipal | https://madarcos.madrid | Joomla 3 + Helix3 / SP Page Builder |
| Urbanismo (trámite) | https://madarcos.madrid/ciudadanos/tramites-personales/169-urbanismo | Página informativa (contacto técnico) |
| Instancias / licencias | https://madarcos.madrid/ciudadanos/tramites-personales/instancias-licencias-y-solicitudes | Instancia general y bonificaciones |
| PGOU / NNSS | https://madarcos.madrid/tu-ayuntamiento/normativa-municipal/plan-general-de-urbanismo | Texto sobre PGOU 2015 en SITCM |
| Ordenanzas | https://madarcos.madrid/tu-ayuntamiento/normativa-municipal/ordenanzas-municipales | PDFs en `/images/Ordenanzas/` |
| Tablón municipal | https://madarcos.madrid/ciudadanos/tablon-municipal | Bandos y concursos (vivienda, minipolígono) |
| Sede electrónica | https://sedemadarcos.eadministracion.es | eAdmin Maggioli (ATM) |
| Tablón sede | https://sedemadarcos.eadministracion.es/PortalCiudadano/Tablon/wfrTablon.aspx | Error sesión / no disponible sin JS |
| Transparencia | https://transparenciamadarcos.eadministracion.es/portal | Portal eAdmin Maggioli |
| Visor SITCM | https://www.madrid.org/cartografia/sitcm/html/visor.htm | Referencia cartográfica CM |

## Cómo se listan expedientes / planeamiento

- **No hay visor urbanístico propio** ni listado de expedientes en HTML.
- **PGOU 2015:** la web indica que está cargado en el Sistema de Información Territorial de la Comunidad de Madrid (SIT/SITCM), aprobado definitivamente en 2015.
- **Normativa:** ordenanzas municipales con PDF embebido (p. ej. IEE publicada en BOCM nº 256/2020).
- **Tablón municipal Joomla:** bandos de adjudicación de vivienda municipal, arrendamiento en minipolígono artesanal, etc.
- **Sede eAdmin:** catálogo de trámites y tablón en SPA; el endpoint `wfrTablon.aspx` devuelve «sesión caducada» sin navegador/JS.

## Cómo se publican licencias

- **No hay dataset ni tablón scrapeable** de licencias concedidas.
- Trámites presenciales mediante **instancia general** (descarga en web) o sede electrónica eAdmin.
- Página de urbanismo solo ofrece contacto del técnico municipal (91 868 14 61).
- El adapter devuelve páginas informativas de trámite (patrón Pozuelo/Berzosa).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes consultadas:**
  - SITCM WFS `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='MADARCOS'` → **0 features**
  - Variante `ILIKE '%MADARCOS%'` → **0 features**
  - La web municipal afirma carga del PGOU en SIT, pero no hay polígonos accesibles vía WFS público para este municipio.
  - Sin ArcGIS, WFS municipal ni GeoJSON en datos abiertos.
- **Estrategia:** centroide municipal + jitter (`centroid: [41.0477311, -3.5821549]`).
- **Limitaciones:** municipio muy pequeño (~50 hab.); planeamiento solo referenciado en SITCM sin geometría WFS expuesta.

## Limitaciones del scrape

- Sede eAdmin Maggioli: SPA + tablón con error de sesión en peticiones directas.
- Transparencia eAdmin: portal SPA sin listado HTML de urbanismo.
- Tablón municipal: artículos sin PDF adjunto scrapeable (contenido mínimo en `articleBody`).
- SSL sede eAdmin: posible cadena CA no verificada → `insecure_ssl: true`.

## Adapter implementado

- **Módulo:** `municipio/adapters/madarcos.py`
- **Fuentes:** Joomla ordenanzas (PDF), PGOU/NNSS, tablón municipal (bandos urbanísticos), páginas informativas sede/trámites.
- **Geometría:** no implementada (`geometry_status: unavailable`).
