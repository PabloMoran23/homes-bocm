# Sant Boi de Llobregat — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.santboi.cat |
| Urbanismo (hub) | https://www.santboi.cat/ajuntament/Urbanisme |
| Planeamiento en trámite | https://www.santboi.cat/planejament-urbanistic/en_tramit |
| Exposición pública | https://www.santboi.cat/planejament-urbanistic/en_exposicio |
| Vigentes | https://www.santboi.cat/planejament-urbanistic/vigents |
| Suspensión licencias | https://www.santboi.cat/planejament-urbanistic/suspesos |
| Gestión urbanística | https://www.santboi.cat/ajuntament/urbanisme/gestio-urbanistica |
| Convenios urbanísticos | https://www.santboi.cat/ajuntament/urbanisme/convenis-urbanistics |
| Sede electrónica | https://tramits.santboi.cat |
| e-Tauler edictes | https://tauler.seu.cat/inici.do?idens=820090004 |
| Autoconsulta urbanística | https://cartoweb.santboi.cat/portal/apps/experiencebuilder/experience/?id=92db6610bab14a69b6a1c5575d14c4e4 |

CMS: **Drupal 10** (meta Generator, tema `boi`).

## Expedientes / planeamiento

- Los listados de planeamiento son páginas índice con `<li><a href="/planejament-urbanistic/{seccion}/{id}">`.
- Cada ficha incluye metadatos en `<li class='codiExpedient'>`, fechas de aprobación/publicación, tipo (AVPR, MPGM, PE, PMU, SUPRA…) y bloque `expedientDocuments` con enlaces a PDF en `http://seu.santboi.cat/docexp/d/...`.
- **Gestión urbanística** y **convenios**: acordeones Bootstrap (`h3.accordion-button`) con fechas en texto y PDFs en `/sites/default/files/...`.
- No hay API JSON pública de expedientes; scrape HTML determinista.

## Licencias de obra

- Tramitación en sede (`tramits.santboi.cat`); carpeta de expedientes del ciudadano requiere certificado.
- **e-Tauler** (Consorci AOC): aplicación React (`tauler.seu.cat`) con edictos de licencias y urbanismo; sin endpoint REST scrapeable sin reverse-engineering del SPA.
- El adapter recoge **fichas informativas** de trámites de obra enlazadas desde la página de urbanismo (sin listado de concesiones con coordenadas).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Experience Builder «Plànol ciutat» / autoconsulta parcelaria (`cartoweb.santboi.cat`, item `92db6610bab14a69b6a1c5575d14c4e4`).
  - MapServer zonificación: `https://cartoweb.santboi.cat/server/rest/services/OD/Planejament_vigent/MapServer` (qualificacions, sin campo expediente).
- **Estrategia:** el visor permite consulta por parcela en UI; no hay query por código de expediente (`X105/2013/001`) ni WFS con ámbitos de plan enlazados a las fichas Drupal.
- **Limitaciones:** polígonos de ámbito solo en PDF/planos; MapServer es capa de qualificació vigent (EPSG:25831), no geometría por proyecto. El orquestador usará centroide municipal + jitter.

## Limitaciones generales

- `en_exposicio` puede estar vacío (formulario de búsqueda Drupal).
- Documentos históricos en `docexp` bajo dominio `seu.santboi.cat` (HTTP en algunos enlaces).
- e-Tauler y sede con tiempos de respuesta elevados en entornos cloud.
