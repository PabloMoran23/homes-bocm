# Navacerrada — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://www.aytonavacerrada.org | OK (WordPress + Elementor) |
| Sede electrónica | https://aytonavacerrada.sedelectronica.es | OK (espublico gestiona) |
| Sede alternativa | https://sedelectronica.aytonavacerrada.org | OK (alias) |
| Urbanismo | https://www.aytonavacerrada.org/urbanismo/ | OK (paginado /urbanismo/2..6) |
| Ordenanzas urbanísticas | https://www.aytonavacerrada.org/ordenanzas-urbanisticas-2/ | OK |
| Normativa urbanística | https://www.aytonavacerrada.org/normativa-urbanistica-2/ | OK (PDFs NNSS 1999) |
| Tablón anuncios | https://aytonavacerrada.sedelectronica.es/board | OK |
| Transparencia | https://aytonavacerrada.sedelectronica.es/transparency | OK (sección 7 Urbanismo) |
| SITCM WFS ámbitos | https://idem.comunidad.madrid/geoserver3/ows | OK |

## Proyectos / expedientes

- **CMS:** WordPress (sitemap XML accesible; REST API parcial)
- **Listado:** `wp-sitemap-posts-post-1.xml` + filtro slug (bando, obras, parcela, urbanismo)
- **Páginas semilla:** `/urbanismo/`, `/ordenanzas-urbanisticas-2/`, `/normativa-urbanistica-2/` — enlaces a PDFs NNSS (planos, memoria, ordenanzas)
- **Sede espublico gestiona:** tablón `/board` con tabla HTML + `preview-document/{uuid}`; transparencia con bloque «URBANISMO Y MEDIO AMBIENTE» (10 docs, carga AJAX)
- **Planeamiento histórico:** 22 ámbitos en SITCM (`DS_NOMB_AMB`: SAU-1..14, UE-1..8) aprobados BOCM 1999-06-02 (NNSS)

## Licencias de obra

- No hay dataset abierto de concesiones con coordenadas
- Información de trámites en web (urbanismo) y sede electrónica
- PDFs normativos en `/normativa-urbanistica-2/` y `/ordenanzas-urbanisticas-2/` (tasa licencias urbanísticas referenciada en ordenanzas)
- Tablón sede publica anuncios puntuales (mayoría no urbanísticas); adapter devuelve páginas de trámite + tablón

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='NAVACERRADA'`
  - 22 features (ámbitos SAU/UE con polígonos)
  - Campo enlace: `DS_NOMB_AMB` (código + nombre sector)
- **Estrategia:** cargar todos los ámbitos SITCM como proyectos con polígono; enriquecer posts WP/board por matching de código SAU/UE en título
- **Limitaciones:**
  - Web sin visor urbanístico propio ni GeoJSON municipal
  - PDFs NNSS sin georreferencia embebida
  - Posts de noticias (obras calle, asfaltado) sin coordenadas en portal
  - SITCM solo cubre ámbitos de planeamiento aprobados (no licencias puntuales)
  - Transparencia urbanismo requiere sesión AJAX (no scrapeada)

## Limitaciones generales

- Dominio histórico `navacerrada.es` no resuelve; usar `aytonavacerrada.org`
- Sitemap grande (~1000 posts); filtro por keywords en slug
- User-Agent identificable requerido; sin dependencia de LLM
