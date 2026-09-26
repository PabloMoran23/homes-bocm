# Estivella — investigación portal ayuntamiento

**Municipio:** Estivella (Valencia, Comunitat Valenciana)  
**Slug:** `estivella`  
**INE:** 46115  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.estivella.es | **Operativa** — Drupal 10 Portales municipales (tema `portales`, Matomo site 206) |
| Planes locales | https://www.estivella.es/es/pagina/planes-locales | **Operativa** — PDFs de planes municipales (PTM, PTG, PLPIF, PMUS, PAMIF, Agenda Urbana) |
| Normas subsidiarias | https://www.estivella.es/es/pagina/normas-subsidiarias-planeamiento | **Operativa** — instrumento de planeamiento |
| Proyectos de ordenanzas | https://www.estivella.es/es/pagina/proyectos-ordenanzas | **Operativa** |
| Noticias | https://www.estivella.es/es/node | Listado Drupal (paginado) |
| Sede electrónica | https://estivella.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://estivella.sedelectronica.es/board | **Operativa** — tabla HTML (~3 filas actuales, sin urbanismo) |
| Catálogo trámites | https://estivella.sedelectronica.es/dossier | Trámites sin histórico público (redirect loop en scrape directo) |
| Consulta expedientes | https://estivella.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Formulario compatibilidad urbanística | https://www.estivella.es/sites/www.estivella.es/files/files/Instancias/sollicitud_compatibilitat_urbanistica.pdf | PDF descargable |

## Planes locales publicados (Drupal)

Página `planes-locales` (25 abr 2025) enlaza PDFs en `/sites/www.estivella.es/files/users/user168/Plans Locals/`:

| Documento | Tipo |
|-----------|------|
| PTM_Estivella_2023f.pdf | Plan Territorial Municipal frente a emergencias |
| PTG del T.M de Estivella_firmado.pdf | Plan Territorial General |
| PLPIF Estivella 2022 | Plan Local de Prevención de Incendios Forestales |
| PMUS Estivella | Plan de Movilidad Urbana Sostenible |
| Plan actuación municipal riesgo sísmico | Plan de riesgo sísmico |
| PAMIF | Plan actuación municipal incendios forestales |
| Agenda Urbana d'Estivella | Agenda urbana |

- **CMS:** Drupal 10 Portales (`/themes/portales`).
- **Listado:** HTML estático con enlaces a PDF; no hay JSON:API pública ni `pagina-aviso` urbanísticos activos (sep 2026).
- **Limitación:** conexiones SSL intermitentes (`handshake timed out`); el adapter reintenta con backoff e `insecure_ssl`.

## Tablón sede (espublico gestiona)

- Plataforma Wicket/YUI (misma que Benigànim, Enguera, Alfafar).
- Columnas: `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- Contenido actual (sep 2026): cens electoral, junta Albalat, jurado — **sin filas urbanísticas ni licencias**.
- Paginación AJAX «Mostrar más»; adapter parsea primera página.

## Licencias de obra

- No hay dataset público de concesiones de licencia de obra mayor/menor.
- Formulario PDF de compatibilidad urbanística en web municipal.
- Trámites de obra vía sede `/dossier` (sin listado histórico).
- El adapter incluye páginas informativas del tablón, catálogo de trámites y formulario (patrón Pozuelo/Benigànim).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - ICV WFS `ms:Planeamiento.Zonificacion` (`https://terramapas.icv.gva.es/0702_Planeamiento`): **0 polígonos** con `cod_ine_mun=46115` tras barrido GML (municipio sin planeamiento en capa ICV).
  - No hay visor urbanístico municipal (ArcGIS, SITUA, etc.) enlazado desde la web.
  - Planes locales publicados solo como PDF sin georreferencia.
- **Estrategia:** sin fuente GIS pública enlazable a expedientes; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:** sin polígonos por expediente; ICV indica régimen art. 17 LUV para municipios sin planeamiento.

## Limitaciones generales

- Web Drupal con timeouts SSL ocasionales en CI (requiere reintentos, `request_delay_s: 0.5`).
- Tablón sede sin entradas urbanísticas en el momento de la investigación.
- Consulta de expedientes requiere login.
- `/dossier` devuelve redirect loop en scrape automatizado sin cookies de sesión.
- Sin geometría enlazable.

## Adapter implementado

- `municipio.adapters.estivella:EstivellaAyuntamientoAdapter`
- Fuentes: páginas Drupal (planes locales, normas subsidiarias) + tablón sede + trámites informativos.
- IDs: `estivella-lic-*` / `estivella-proy-*` (sha256[:14]).
