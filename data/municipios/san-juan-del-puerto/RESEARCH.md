# San Juan del Puerto — investigación portal ayuntamiento

Municipio: **San Juan del Puerto** (`san-juan-del-puerto`)  
Provincia: Huelva · CCAA: Andalucía · INE: **21059** · Boletín: BOJA

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web municipal (WordPress / Elementor) | https://sanjuandelpuerto.es | Urbanismo, exposición pública, modelos DR |
| Urbanismo | https://sanjuandelpuerto.es/servicios-publicos/urbanismo/ | Ordenanzas DR/comunicaciones previas (tablas Elementor) |
| Plan movilidad sostenible | https://sanjuandelpuerto.es/servicios-publicos/urbanismo/plan-de-movilidad-sostenible/ | Documentación planeamiento movilidad |
| Exposición pública | https://sanjuandelpuerto.es/ayuntamiento/exposicion-publica/ | Enlace a transparencia sede |
| Documentos / modelos | https://sanjuandelpuerto.es/ayuntamiento/documentos/ | DR obra, ocupación, utilización |
| Sede electrónica (espublico gestiona) | https://sanjuandelpuerto.sedelectronica.es | Wicket + cookie jar |
| Tablón de anuncios | https://sanjuandelpuerto.sedelectronica.es/board/ | ~10 anuncios visibles; urbanismo esporádico (PMCC, expropiaciones) |
| Catálogo trámites | https://sanjuandelpuerto.sedelectronica.es/dossier | Competencia 3.01 Urbanismo y Vivienda |
| Transparencia urbanismo | https://sanjuandelpuerto.sedelectronica.es/transparency/9b4f2ebd-8218-478f-8d2e-031359cf6bdb/ | Sección 7 (61 ítems, carga parcial AJAX) |
| Consulta expedientes | https://sanjuandelpuerto.sedelectronica.es/expedientes | Requiere Cl@ve / certificado |
| SITUA PGOU | https://ws132.juntadeandalucia.es/situadifusion/pages/planeamientoGeneralCompartir.jsf?municipiosSeleccionados=21059&codigosMunicipios=21059 | Planeamiento general |
| SITUA búsqueda | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Índice autonómico |
| VITUA | https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ | Visor territorial JdA |

## Cómo se listan expedientes / proyectos

- **Tablón sede**: tabla HTML (`class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`). Enlaces `/preview-document/{uuid}`. Entradas recientes incluyen Plan Municipal Cambio Climático (872/2025), expropiaciones infraestructura (2084/2021).
- **Catálogo `/dossier`**: procedimientos espublico (`/catalog/t/{uuid}`): licencias obra/actividad, modificaciones planeamiento, actuaciones urbanísticas, etc. Sin histórico de resoluciones.
- **Transparencia**: árbol Wicket; sección 7 «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE (61)» enlazada desde la web de exposición pública.
- **Web WP**: páginas de urbanismo y exposición pública; PDFs en `/wp-content/uploads/` cuando existen.
- **Planeamiento**: modificaciones (p. ej. PP5 Camino de Gibraleón) publicadas en BOJA y referenciadas en sede durante IP; PGOU en SITUA.

## Cómo se publican licencias

- No hay dataset ni API de licencias concedidas.
- Concesiones deberían publicarse en el **tablón**; actualmente sin entradas explícitas de licencia de obra recientes.
- **Trámites** en catálogo sede (solicitud licencia obra, actividad, DR, ocupación, etc.).
- **Modelos** de declaración responsable en la web municipal (`/ayuntamiento/documentos/`).
- Consulta de expedientes con autenticación en `/expedientes`.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - VITUA: visor autonómico por municipio, sin enlace por código de expediente del tablón.
  - SITUA: documentación PDF del PGOU y modificaciones; sin GeoJSON por expediente municipal.
  - No hay visor urbanístico municipal, ArcGIS local ni WFS del ayuntamiento.
- **Estrategia:** centroide municipal en manifest (`centroid: [37.3166, -6.8394]`) + jitter en geocode.
- **Limitaciones:** tablón y transparencia son PDFs/HTML sin coordenadas; expedientes en sede requieren login.

## Limitaciones

- Tablón con predominio de anuncios administrativos (empleo, elecciones).
- Transparencia urbanismo requiere interacción Wicket/AJAX para listado completo.
- `/dossier` necesita cookie jar HTTP (redirect interno espublico).
- Sin listado público histórico de licencias ni geometría enlazable por expediente.
