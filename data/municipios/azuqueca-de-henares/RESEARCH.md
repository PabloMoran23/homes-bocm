# Azuqueca de Henares — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.azuqueca.es |
| Urbanismo | https://www.azuqueca.es/servicios/urbanismo |
| Planeamiento (POM, PP, estudios detalle) | https://www.azuqueca.es/servicios/urbanismo/planeamiento |
| Gestión y ejecución | https://www.azuqueca.es/servicios/urbanismo/gestion-y-ejecucion |
| Información de interés | https://www.azuqueca.es/servicios/urbanismo/informacion-de-interes |
| Licencias / trámites | https://www.azuqueca.es/servicios/urbanismo/licencias-declaraciones-y-comunicaciones |
| Sede electrónica | https://azuqueca.sedelectronica.es |
| Tablón de anuncios | https://azuqueca.sedelectronica.es/board |
| Catálogo trámites | https://azuqueca.sedelectronica.es/dossier |
| Transparencia (sección urbanismo) | https://azuqueca.sedelectronica.es/transparency |
| Consulta expedientes (login) | https://azuqueca.sedelectronica.es/expedientes |

## CMS y listado de expedientes / planeamiento

- **Portal corporativo:** Liferay (Document Library bajo `/documents/37218/...`).
- **Planeamiento:** listado estático en HTML con enlaces directos a PDF (tomos POM, modificaciones, planes parciales SUR-R1…R9, estudios de detalle por manzana/parcela, plan especial Miralcampo).
- **No hay** listado paginado de expedientes urbanísticos abiertos en la web; la sede `/expedientes` exige identificación electrónica.
- **Tablón espublico:** tabla Wicket en `/board` con `preview-document/{uuid}`; categoría «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» en transparencia (pocos anuncios recientes en primera página).
- **Licencias:** no hay dataset de concesiones; solo fichas de trámite (`/-/licencia-urbanística-de-obra`, declaración responsable, etc.) y presentación vía sede.

## Licencias de obra

- Publicación: páginas informativas Liferay + catálogo sede (`/dossier`, enlaces `/catalog/t/...` cuando responde).
- Sin tablón sistemático de licencias concedidas con dirección/coordenadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - «Plano de Azuqueca de Henares» en urbanismo: PDF callejero A3, sin servicio SIG enlazable a expediente.
  - Planes parciales y estudios de detalle: solo PDF cartográfico, sin API/WFS municipal.
  - No visor ArcGIS/WFS público del ayuntamiento para consulta por código de expediente.
  - Sede `/expedientes` y visores internos: requieren autenticación.
- **Estrategia adapter:** metadatos desde PDFs Liferay + tablón; geocode del orquestador (centroide municipal + jitter).
- **Limitaciones:** geometría de ámbito solo en planos PDF no georreferenciados automáticamente; sin join expediente↔polígono.

## Limitaciones generales

- SSL sede: certificado válido; `insecure_ssl` por compatibilidad con patrón espublico en otros municipios.
- `/dossier` puede tardar >60s; el adapter tolera fallo parcial del catálogo.
- Tablón mezcla anuncios no urbanísticos; filtros regex en adapter.
