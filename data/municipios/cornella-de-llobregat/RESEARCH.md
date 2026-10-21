# Cornellà de Llobregat — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL | Uso |
|--------|-----|-----|
| Web corporativa (Plone) | https://www.cornella.cat | Carpetas `files/contenidos/Urbanisme`, `InfoPublica`, boletín *Cornellà informa* (`*_urbanismo.pdf` en sitemap) |
| Govern obert | http://governobert.cornella.cat/altres | Tablón de anuncios e información pública (HTML) |
| Normativa en trámite | http://governobert.cornella.cat/normativa-municipal-en-tramit | Consultas previas, IP, aprobaciones provisionales/definitivas |
| Seu-e (transparencia) | https://seu-e.cat/web/cornella/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme | Índice urbanismo + enlaces RPUC/MUC |
| Sede electrónica | https://seuelectronica.cornella.cat/portal/inicio.do?ent_id=1&idioma=1 | Trámites (carpeta ciudadana); muy lento desde algunas redes |
| Trámites web | https://www.cornella.cat/ca/tramits/seu-electronica | Acceso a sede |

## Proyectos / expedientes

- **Listado:** no hay API JSON pública del ayuntamiento. Los expedientes de planeamiento se consultan en **RPUC** (Generalitat) filtrando municipio INE `08073`.
- **Plone:** documentos PDF en `Urbanisme/` (PAISI Sant Ildefons, Pla Central, Fontsanta, edictes, ascensors) e `InfoPublica/` (p. ej. ordenanza ZBE/circulación 2020).
- **Govern obert:** bloques HTML por fase (consulta previa, información pública, aprobación inicial/provisional/definitiva) con fechas y enlaces a PDF en `cornella.cat/files/…`.
- **Sitemap:** `https://www.cornella.cat/sitemap.xml.gz` — cientos de PDF históricos `Cornella informa/*_urbanismo.pdf`.

## Licencias de obra

- No hay listado público estructurado de licencias concedidas (como tablón Sedipualba en otros municipios).
- Trámites: sede electrónica + ordenanza de **obres menors** (PDF en normativa Plone).
- El adapter registra páginas informativas de trámite y anuncios del govern obert que mencionan licencias/obras cuando el host responde.

## Geometría / visor

- **geometry_status:** `unavailable` (sin WFS/ArcGIS REST enlazable por expediente desde el portal municipal).
- **Fuentes cartográficas (referencia, no automatizadas):**
  - Visor MUC: https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08073
  - RPUC expedientes: https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08073
  - Refós planeamiento AMB: https://www.amb.cat/s/web/territori/urbanisme/refos-del-planejament.html
- **Estrategia adapter:** metadatos + URL de visor/RPUC como filas de referencia; el orquestador aplica centroide municipal + jitter (`centroid` en manifest).
- **Limitaciones:** visor MUC es aplicación Java interactiva sin query REST por código de expediente; governobert y seuelectronica a menudo inaccesibles o lentos desde entornos cloud (timeout).

## Limitaciones operativas

- `governobert.cornella.cat` y `seuelectronica.cornella.cat` pueden no responder en &lt;12–45 s desde datacenters (documentado; el scrape sigue con Plone + sitemap).
- RSS de carpetas Plone (`edictes`, `InfoPublica`) casi vacíos; el crawl BFS de carpetas es más fiable.
- Muchos PDF del sitemap son históricos (2002–2008 *Cornellà informa*); se filtran por palabras clave urbanísticas.
