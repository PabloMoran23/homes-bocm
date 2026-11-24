# Morón de la Frontera — investigación portal ayuntamiento

## Fuentes base

| Recurso | URL | Formato |
|---------|-----|---------|
| Web municipal | https://www.morondelafrontera.es | CMS eXisto (Bootstrap/jQuery) |
| Sede electrónica | https://morondelafrontera.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://morondelafrontera.sedelectronica.es/board/ | HTML tabla (~10 filas visibles, preview-document PDF) |
| Transparencia | https://morondelafrontera.sedelectronica.es/transparency | Carpetas AJAX (Urbanismo: 556 docs, Info pública: 29) |
| Urbanismo (web) | https://www.morondelafrontera.es/es/servicios-municipales/urbanismo-y-planificacion-estrategica | Texto PGOU/NNSS, enlace sede |
| Formularios | https://www.morondelafrontera.es/servicios-municipales/servicio-atencion-a-la-ciudadania/formularios-descargables | PDFs estáticos (/contenidos/web/0/*.pdf) |
| POU (LISTA) | https://morondelafrontera.nuevoplan.es | WordPress Flatsome + REST `/wp-json/wp/v2/media` |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41061 | Consulta planeamiento digitalizado (INE 41061) |

## Expedientes / planeamiento

- **Instrumento vigente:** PGOU = adaptación parcial NNSS (aprobación definitiva 23/03/2009, BOP 01/07/2009); NNSS 1982/1991 subsidiarias según web.
- **En tramitación:** POU adaptado a LISTA (portal nuevoplan, fase 2); documentos vía WP media.
- **Tablón:** mezcla anuncios generales; filas urbanísticas filtradas por regex (licencias, planeamiento, información pública).
- **Transparencia:** carpetas relevantes indexadas (sin descarga masiva AJAX de 556 PDFs en el adapter).
- **Licencias concedidas:** no hay listado público tabular de concesiones; formularios de solicitud + tablón para edictos.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No hay visor urbanístico municipal (ArcGIS/WFS) enlazado a expedientes. El SIU estatal (`mapas.fomento.gob.es` Planeamiento_Vigente) cubre planeamiento a escala nacional pero no enlaza códigos de expediente del ayuntamiento.
- **Estrategia:** Orquestador aplicará centroide municipal + jitter (`manifest.portal.config.centroid`).
- **Limitaciones:** Transparencia y expedientes requieren navegación Wicket AJAX; geometría de ámbito no publicada en APIs abiertas del ayuntamiento.

## Limitaciones técnicas

- Sede: redirección `info.1` → `info.0`; peticiones deben seguir cookies JSESSIONID.
- Tablón muestra página corta (no paginación REST pública identificada).
- `catalog` / `citizen-service` no disponibles en esta sede (404).
- Sin boletín regional asociado en cola (`bocm_count: 0`).
