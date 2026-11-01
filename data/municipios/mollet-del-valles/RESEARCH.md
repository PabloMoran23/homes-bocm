# Mollet del Vallès — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|--------|
| Web municipal (Plone) | https://www.molletvalles.cat | CloudFront bloquea UA genérico; requiere User-Agent identificable |
| Urbanisme | https://www.molletvalles.cat/ca/serveis/urbanisme | Minisite Plone |
| POUM | https://www.molletvalles.cat/ca/serveis/urbanisme/poum-de-mollet | PDFs + enlaces geoportal |
| Notícies urbanisme RSS | https://www.molletvalles.cat/ca/serveis/urbanisme/noticies/noticies/rss.xml | Noticias con planeamiento/obras |
| Cerca Plone | https://www.molletvalles.cat/ca/@@search?SearchableText=planejament | Paginación `b_start:int` |
| RSS cerca | https://www.molletvalles.cat/ca/search_rss?SearchableText=planejament | |
| Catàleg de mapes / geoportal | https://www.molletvalles.cat/ca/la-ciutat/cataleg-de-mapes/geoportal-urbanistic | Enlace a visor Nexus |
| Seu electrònica | https://seu.molletvalles.cat | Plataforma propia (no opensiac) |
| Tràmits | https://tramits.molletvalles.cat/Ciutadania/TramitsTemes.aspx | Tema «Obres, urbanisme i habitatge» |
| Transparència projectes normatius | https://transparencia.molletvalles.cat/ca/informacio-publica/accio-de-govern-i-normativa/normativa-plans-i-programes/memories-i-documents-dels-projectes-normatius-en-curs | Plone FGC |
| e-Tauler | https://tauler.seu-e.cat/inici?idEns=812490004 | Código ens 812490004 |

## Expedientes / planeamiento

- **Listado:** no hay tabla pública de expedientes urbanísticos en la sede (sin STA `PTS2_TABLON` ni `infopublica`).
- **Fuentes usadas:** RSS y búsqueda Plone (noticias POUM, sectores, suspensiones), documentación POUM (PDFs), enlaces geoportal, carpetas de transparencia (consultas públicas / memorias normativas con relevancia urbanística filtrada).
- **Formato:** HTML Plone + RSS 2.0; PDFs estáticos; trámites informativos ASP.NET.

## Licencias de obra

- No se publica listado de licencias concedidas (fechas, direcciones).
- **Catàleg de tràmits:** páginas informativas (`DetallTramit.aspx?IdTramit=164` licencias urbanísticas, `153` obres, `58/30/203` informes INUR/INUA/INCU).
- Carpetas ciudadanas (`eserveis.molletvalles.cat`) requieren autenticación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Geoportal urbanístic Nexus: `https://mun.nexusgeographics.com/molletgp42/visor/geoportal` (enlazado desde POUM; capas planejament aplicable, sectors, qualificació, suspensió llicències). Coordenadas internas EPSG:25831 en URL (`centre=432777,4600200`).
  - AMB `Planejament/Expedients/MapServer/3` con `CODI_INE='08120'`: **0 features** (sin geometría de expedientes metropolitanos).
- **Estrategia:** sin join expediente↔polígono en fuentes públicas; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** visor Nexus devuelve 404 desde el entorno cloud del agente (posible restricción de red); no hay WFS/ArcGIS con código de expediente; listados son noticias/PDFs sin georreferencia.

## Limitaciones generales

- CloudFront en `www.molletvalles.cat` sin User-Agent adecuado → 403.
- Sin boletín BOCM asociado en cola (`bocm_count: 0`).
- Transparencia mezcla ordenanzas no urbanísticas (filtradas en adapter).
