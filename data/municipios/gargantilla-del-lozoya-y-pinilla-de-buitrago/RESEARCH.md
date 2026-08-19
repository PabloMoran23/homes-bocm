# Gargantilla del Lozoya y Pinilla de Buitrago — investigación portal ayuntamiento

**Municipio:** Gargantilla del Lozoya y Pinilla de Buitrago (Comunidad de Madrid)  
**Slug:** `gargantilla-del-lozoya-y-pinilla-de-buitrago`  
**Portal base:** https://gargantillaypinilla.madrid

## Resumen

Municipio fusionado (Gargantilla del Lozoya + Pinilla de Buitrago) con web municipal **WordPress + Elementor**
(`gargantillaypinilla.madrid`) y sede electrónica **espublico gestiona**
(`gargantillaypinilla.sedelectronica.es`). El planeamiento se publica principalmente en la página del
**PGOU** (aprobación inicial 2022, exposición documentación provisional) y en **ordenanzas** con anuncios BOCM.
Los ámbitos del PGOU están en el visor SIT de la Comunidad de Madrid (WFS).

## Fuentes

| Recurso | URL | Formato | Contenido urbanístico |
|---------|-----|---------|----------------------|
| Web municipal | `https://gargantillaypinilla.madrid` | WordPress Elementor | Portal principal |
| PGOU | `https://gargantillaypinilla.madrid/plan-general-de-ordenacion-urbana/` | HTML + PDFs | Aprobación inicial/provisional PGOU, informe alegaciones, resumen modificaciones |
| Ordenanzas | `https://gargantillaypinilla.madrid/ordenanzas/` | HTML + PDFs | Ordenanzas fiscales/urbanísticas, anuncios BOCM (plusvalías, tasas licencias, ocupación suelo) |
| Documentos municipales | `https://gargantillaypinilla.madrid/documentos-municipales/` | PDFs | Solicitud licencia obra, DR obras |
| Transparencia | `https://gargantillaypinilla.madrid/transparencia/` | WordPress | Enlaces a sede transparencia |
| Sede electrónica | `https://gargantillaypinilla.sedelectronica.es` | espublico gestiona | Trámites, expedientes, tablón |
| Tablón sede | `https://gargantillaypinilla.sedelectronica.es/board/` | HTML espublico | Tablón de anuncios (vacío ago 2026) |
| Transparencia sede | `https://gargantillaypinilla.sedelectronica.es/transparency/` | Wicket | Portal transparencia |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 8 polígonos `DS_NOMB_AMB` (POLÍGONO 1–7) para `DS_MUNICIPIO='GARGANTILLA DEL LOZOYA Y PINILLA DE BUITRAGO'` |
| Visor SITCM | `https://gestiona.comunidad.madrid/cartografia/visor_sit.html` | ArcGIS/WFS | Planeamiento municipal (enlace desde comunidad.madrid) |

## Cómo se listan expedientes

- **PGOU:** página dedicada con texto expositivo y enlaces a PDFs (informe conclusiones alegaciones, resumen modificaciones). Sin listado estructurado de expedientes individuales.
- **Ordenanzas:** listado HTML de PDFs descargables; varios son anuncios BOCM de aprobación de ordenanzas/tasas urbanísticas.
- **Tablón sede:** tabla HTML espublico (`/board/`) — actualmente sin filas publicadas.
- **API REST WP:** `https://gargantillaypinilla.madrid/wp-json/wp/v2/pages` para descubrir páginas.

## Licencias de obra

- No hay listado público de licencias concedidas.
- Formularios en `documentos-municipales/`: solicitud licencia obra, declaración responsable obras.
- Trámites en sede `/dossier` (sin listado scrapeable de concesiones).
- Adapter devuelve páginas informativas de trámites + tablón sede.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='GARGANTILLA DEL LOZOYA Y PINILLA DE BUITRAGO'` (`srsName=EPSG:4326`)
  - 8 features: POLÍGONO 1–7 (polígonos de suelo urbano del PGOU)
  - Visor web: `https://gestiona.comunidad.madrid/cartografia/visor_sit.html` (sin API directa por expediente)
- **Estrategia:**
  - Cargar todos los polígonos WFS como proyectos de ámbito SIT
  - Enriquecer proyectos WP/BOCM con geometría por coincidencia de nombre (`POLÍGONO N`, ILIKE en `DS_NOMB_AMB`)
- **Limitaciones:**
  - Sin geometría por expediente individual (solo polígonos PGOU)
  - Tablón sede vacío; licencias sin coords
  - PDFs PGOU sin georreferencia embebida

## Limitaciones generales

- Sede `gargantilladellozoya.sedelectronica.es` (dominio antiguo) devuelve página de selección; usar `gargantillaypinilla.sedelectronica.es`.
- Tablón de anuncios electrónico sin contenido (ago 2026).
- Sin visor urbanístico propio del ayuntamiento; dependencia del SITCM regional.

## Adapter

- Módulo: `municipio/adapters/gargantilla_del_lozoya_y_pinilla_de_buitrago.py`
- Patrón: `villavieja_del_lozoya.py` / `venturada.py` (WP Elementor + espublico sede + SITCM WFS partial)
- IDs: `gargantilla-del-lozoya-y-pinilla-de-buitrago-{lic|proy}-{sha256[:14]}`
