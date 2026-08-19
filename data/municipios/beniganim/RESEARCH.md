# Benigànim — investigación portal ayuntamiento

**Municipio:** Benigànim (Valencia / València, Comunitat Valenciana)  
**Slug:** `beniganim`  
**Boletín:** DOGV (`dogv`, 3 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.beniganim.es | **Operativa** — Drupal 10 Portales municipales (tema `portales`) |
| Avisos / anuncios | https://www.beniganim.es/va/pagina-aviso/* | **Operativa** — modificaciones PGOU, planes especiales, licencia ambiental |
| Plànol municipal | https://www.beniganim.es/va/pagina/planol-beniganim | PDF descargable (no visor interactivo) |
| Trámites | https://www.beniganim.es/va/pagina/tramits-municipals | Listado general de trámites |
| Sede electrónica | https://beniganim.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://beniganim.sedelectronica.es/board/ | **Operativa** — tabla HTML (~4 filas actuales, sin urbanismo) |
| Catálogo trámites | https://beniganim.sedelectronica.es/dossier | Trámites sin histórico público |
| Consulta expedientes | https://beniganim.sedelectronica.es/expedientes | Requiere autenticación |
| ADL Diputación | https://beniganim.divaladl.es/va/inicio/index | Portal ADL (empleo/formación); no urbanismo |
| Transparencia | https://www.beniganim.es/es/transparencia/acces-informacio | Portal transparencia Portales |

## Avisos Drupal (urbanismo / planeamiento)

El ayuntamiento publica expedientes de planeamiento como **páginas de aviso** (`pagina-aviso`), enlazadas desde la home en catalán (`/va`):

| Slug | Título | Tipo |
|------|--------|------|
| `modificacio-puntual-no-10-del-pgou` | Modificación puntual nº 10 del PGOU | modificación PGOU |
| `modificacio-puntual-num-12-del-pgou` | Modificación puntual núm. 12 del PGOU | modificación PGOU |
| `modificacio-puntual-num-13-del-pgou` | Modificación puntual núm. 13 del PGOU | modificación PGOU |
| `versio-preliminar-pla-especial-proteccio-lesglesia-sant-miquel-arcangel` | Pla especial protección iglesia | plan especial |
| `cataleg-proteccions-pla-especial-proteccio-lesglesia-sant-miquel-arcangel-beniganim` | Catálogo de protecciones | plan especial |
| `anunci-sollicitud-llicencia-ambiental` | Solicitud licencia ambiental | licencia ambiental |
| `pla-urba-dactuacio-municipal` | Pla urbà d'actuació municipal | plan de actuación |
| `consulta-publica-previous-pla-especial-de-minimitzacio-dimpacte-territorial` | Consulta pública plan especial | consulta pública |
| `consulta-previa-modificacio-catalog-de-bens` | Consulta previa catálogo de bienes | consulta previa |

- **CMS:** Drupal 10 Portales (`/themes/portales`), Matomo site 141.
- **Listado:** no hay JSON:API pública; el adapter descubre enlaces `pagina-aviso` en `/va` y `/es` + semillas configuradas.
- **Documentos:** PDFs embebidos en páginas de aviso (`/sites/www.beniganim.es/files/...`).
- **Limitación:** conexiones intermitentes (`Connection reset`) desde CI; el adapter reintenta con backoff.

## Tablón sede (espublico gestiona)

- Misma plataforma Wicket que Coín, Cómpeta, Humanes.
- Columnas: `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- Contenido actual (ago 2026): nomenamientos, padrón fiscal, festivo local, convenios — **sin filas urbanísticas**.
- Paginación AJAX «Mostrar más»; adapter parsea primera página.

## Licencias de obra

- No hay dataset público de concesiones de licencia de obra mayor/menor.
- Licencia **ambiental** publicada como aviso Drupal.
- Trámites de obra vía sede `/dossier` (sin listado histórico).
- El adapter incluye páginas informativas del tablón y catálogo de trámites (patrón Pozuelo/Coín).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Plànol municipal: https://www.beniganim.es/va/pagina/planol-beniganim — PDF estático del municipio, sin enlace a expedientes.
  - Visor sòl industrial CV (Generalitat): referenciado en ADL Diputación; ámbito regional industrial, no expedientes municipales.
  - No hay ArcGIS MapServer/WFS municipal con campo de expediente.
- **Estrategia:** los avisos y tablón son PDF/HTML sin georreferencia; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:** sin polígonos por expediente; visor cartográfico interactivo no localizado.

## Limitaciones generales

- Web Drupal con resets de conexión ocasionales en CI (requiere reintentos).
- Tablón sede sin entradas urbanísticas en el momento de la investigación.
- Consulta de expedientes requiere login.
- Sin geometría enlazable.

## Adapter implementado

- `municipio.adapters.beniganim:BeniganimAyuntamientoAdapter`
- Fuentes: avisos Drupal + tablón sede + trámites informativos.
- IDs: `beniganim-lic-*` / `beniganim-proy-*` (sha256[:14]).
