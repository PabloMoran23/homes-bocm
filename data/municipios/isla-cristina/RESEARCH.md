# Isla Cristina — investigación portal ayuntamiento

## URLs base y páginas semilla

| Rol | URL |
|-----|-----|
| Web actual (WordPress/Astra) | https://islacristinaweb.org/ |
| Obras y urbanismo (formularios PDF) | https://islacristinaweb.org/obras-y-urbanismo/ |
| Delegación urbanismo | https://islacristinaweb.org/servicio-municipal-de-obras-y-urbanismo/ |
| Web legacy (PGOU, convenios) | http://wp.islacristina.org/ |
| PGOU (enlaces normas/planos) | http://wp.islacristina.org/pgou-isla-cristina/ |
| Urbanismo y obras públicas | http://wp.islacristina.org/urbanismo-y-obras-publicas/ |
| Agenda urbana / EDUSI | https://agendaurbana.islacristina.org/ |
| Sede electrónica (espublico gestiona) | https://islacristina.sedelectronica.es/ |
| Tablón de anuncios | https://islacristina.sedelectronica.es/board |
| Catálogo de trámites | https://islacristina.sedelectronica.es/dossier.2 |
| Portal transparencia | https://islacristina.sedelectronica.es/transparency |
| SITUA (INE 21043) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=21043 |
| PGOU en SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/planeamientoGeneralCompartir.jsf?municipiosSeleccionados=21043&codigosMunicipios=21043 |
| VITUA (Junta) | https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ |
| PDC Diputación Huelva | https://pdc.diphuelva.es/P2104300D |

## Cómo se listan expedientes / proyectos

- **Tablón sede** (`/board`): tabla HTML Wicket con columnas expediente, procedimiento, categoría, fecha y enlace `preview-document`. En la revisión (nov 2026) predominan anuncios de personal; licencias urbanísticas aparecen de forma esporádica.
- **Catálogo de trámites** (`dossier.2`): listado de servicios electrónicos (licencias de obra, DR, planeamiento, actuaciones urbanísticas). No expone concesiones históricas, solo fichas de trámite.
- **Transparencia** (`/transparency`): carpetas documentales; la sección *Urbanismo, Obras Públicas y Medio Ambiente* agrupa ~109 documentos (índice visible cuando la sede responde; puede tardar por TLS).
- **Web municipal**: PGOU (RA-PGOU CP-158/2012, aprobación 2013), estudios de detalle, convenios (p. ej. LIDL), PMVS, EDUSI — principalmente PDFs enlazados desde `wp.islacristina.org` y la nueva web.
- **Consulta de expedientes** en sede requiere autenticación (Carpeta ciudadana); no hay API pública de expedientes urbanísticos abiertos.

## Licencias de obra

- No hay dataset público de concesiones con dirección/coordenadas.
- Formularios y modelos en `obras-y-urbanismo` (licencia mayor, DR de obras, DR de ocupación, licencias de apertura/actividad).
- Trámites electrónicos en sede (p. ej. *Solicitud de Licencia de Obra Mayor*, *Declaración Responsable para ejecución de Obras*).
- El adapter registra páginas informativas + entradas del catálogo y formularios; filas del tablón cuando el título encaja con licencia/actividad.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - VITUA (visor autonómico LISTA/SITUA): capas de instrumentos de ordenación; no hay API estable documentada en el portal municipal para enlazar expediente → polígono.
  - PDC Huelva (`P2104300D`): cartografía/planeamiento provincial.
  - PGOU en web/SITUA: documentación y planos en PDF, sin GeoJSON por expediente.
  - No existe visor municipal tipo Ayamonte (Leaflet/JS con capas descargables).
- **Estrategia:** sin `geom_geojson` en filas del adapter; el orquestador aplica centroide municipal (`centroid` en manifest) + jitter en geocode.
- **Limitaciones:** sede con timeouts SSL intermitentes en `/transparency` y `/dossier`; tablón sin coords; licencias solo como edictos PDF.

## Limitaciones generales

- Hosts mixtos HTTP/HTTPS (`wp.islacristina.org` vs `islacristinaweb.org`).
- `insecure_ssl: true` en sede por robustez ante handshake lento.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
