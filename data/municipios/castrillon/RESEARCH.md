# Castrillón (Asturias) — investigación portal

## URLs base y semillas

- **Web municipal:** https://castrillon.es (Joomla; pie Tailwind; sección **Territorio → Urbanismo**).
- **Sede electrónica (Sedipualba):** https://sede.castrillon.es — tablón RSS, catálogo de trámites (área Urbanismo lista vacía en ciudadanía; conviene **todas las ámbitos** para trámites reales).
- **RPGUR (Registro de planeamiento, Principado):** enlace desde urbanismo municipal a búsqueda pública con `idConcejo=16`, método `listPublico`.
- **Visor regional:** https://sigvisor.asturias.es/visorurbanismo/ (enlace informativo desde el ayuntamiento).
- **Plenos / actas en web:** https://castrillon.es/plenos — artículos con orden del día; líneas `Expediente …:` en HTML.

## Cómo se listan expedientes / planeamiento

| Fuente | Formato | Uso |
|--------|---------|-----|
| RPGUR (`/rpgur/action/publico/busquedaConsulta`) | HTML tabla (instrumentos vigentes por concejo) | Lista canónica de instrumentos urbanísticos regionales |
| Plenos municipales (`/plenos/...`) | HTML (`<li>Expediente …`) | Expedientes de agenda municipal (ordenanzas, tasas urbanísticas, suelo, etc.) |
| Página Urbanismo municipal | HTML + enlaces externos | Puntero a RPGUR y visor |

## Licencias de obra

No hay **listado abierto de licencias concedidas** en el portal analizado. La sede expone **tablón de anuncios** (RSS) y **trámites**; el catálogo “Urbanismo / ciudadanía” puede aparecer sin procedimientos listados según ámbito.

**Estrategia en adapter:** filas informativas (portal + tablón RSS cuando el título sugiere licencias/urbanismo) + nota de que no son concesiones.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS GeoServer del visor RPGUR — `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`, capa `n01_AMBITO_INSTRUMENTO_CONSULTAS`, filtro CQL `id_municipio=33016` (INE Castrillón), enlace de polígono al inventario RPGUR vía `Id._Inventario_Registro_Urbanístico`.
- **Estrategia:** para cada fila RPGUR con `id_instrumento`, cruzar con features WFS por ID inventario; centroide WGS84 para `lat`/`lon` si hay geometría.
- **Limitaciones:** desde este entorno **www54.asturias.es** y **visorrpgur:8090** pueden **no responder** (timeout/firewall); en ese caso no hay `geom_geojson` y el geocode usa centroide municipal + jitter. El visor `sigvisor.asturias.es` no se usa como API (solo referencia humana).

## Limitaciones generales

- RPGUR y WFS dependen de conectividad al Principado; reintentar desde red sin restricciones.
- Plenos: solo expedientes cuyo texto coincide con heurística urbanística/obra/licencias.
- PDFs de actas no enlazados de forma estable en la muestra scrapeada; se prioriza HTML del artículo.
