# Investigación portal — San Javier (Murcia)

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.sanjavier.es |
| Urbanismo (información) | https://www.sanjavier.es/es/seccion-49-urbanismo-administrativo |
| Planeamiento (listado Yii) | https://www.sanjavier.es/es/ayuntamiento-planteamiento-urbanistico |
| Edictos (redirige a sede) | https://www.sanjavier.es/es/ayuntamiento-edictos |
| Sede electrónica | https://sanjavier.sedelectronica.es |
| Tablón de anuncios | https://sanjavier.sedelectronica.es/board |
| Trámites (catálogo) | https://sanjavier.sedelectronica.es/dossier |
| URBMURCIA (enlaces web) | https://urbmurcia.carm.es/web/urbmurcia/expedientes/consulta-general |
| BORM (histórico NN.SS.) | https://www.borm.es |

La web corporativa usa **Yii** (listviews con paginación `yw2_page`, descargas `descargar-fichero-*`). Los edictos municipales ya no se listan en la web: un único aviso remite al **tablón de la sede** (espublico gestiona / Wicket).

## Licencias de obra

- **Publicación:** edictos en tablón sede (`/board`) — filas HTML con `class_name`, `class_folderName`, `preview-document/{uuid}`.
- **Trámites:** urbanismo administrativo en web (`seccion-49`) con modelos de declaración responsable y comunicación previa (PDF); sede `/dossier` para iniciar trámites (requiere identificación).
- No hay dataset CSV/API de licencias concedidas; el adapter incluye páginas informativas + filas del tablón que coinciden con regex de licencia/obra.

## Proyectos / planeamiento

| Origen | Formato | Notas |
|--------|---------|-------|
| Tablón sede | HTML tabla espublico | Modificaciones NN.SS., IP concesiones demaniales, planeamiento |
| Listado planeamiento web | Yii list items + PDF adjuntos | NN.SS. vigentes, PGMO en tramitación |
| Sección urbanismo | Enlaces PDF + URBMURCIA/BORM | Documentación PGMO, modificaciones, cartografía |
| URBMURCIA | Portal JSF | Consulta expedientes de planeamiento regional; no scrapeado (sesión/UI) |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS CARM `SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo` filtrado `Municipio='San Javier'` (EPSG:4326 GeoJSON).
  - Campos útiles: `Ambito`, `Clasificacion`, `Enlace_ficha`.
  - URBMURCIA / SITMurcia visores web enlazados desde la sección urbanismo (sin WFS por expediente municipal).
- **Estrategia:** tras extraer título/edicto, emparejar tokens de ámbito (`Polígono…`, `La Manga`, `Santiago de la Ribera`, etc.) con polígonos WFS; rellenar `geom_geojson` cuando hay match.
- **Limitaciones:** el tablón no enlaza geometría por código de expediente; muchos anuncios son administrativos sin ámbito explícito; URBMURCIA no expone API estable para scraping masivo.

## Limitaciones generales

- Tablón sede muestra ~10 anuncios recientes por página (sin paginación pública obvia en HTML estático).
- Consulta de expedientes en sede requiere identificación electrónica.
- STA contribuyente (`sede.sanjavier.es`) es distinta de la sede de trámites (`sanjavier.sedelectronica.es`).
