# El Campello — investigación portal ayuntamiento

## Municipio

- **Nombre:** El Campello
- **Slug:** `el-campello`
- **Provincia:** Alicante
- **Comunidad Autónoma:** comunitat-valenciana
- **Boletín:** DOGV (`dogv`, 4 proyectos BOCM legacy)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.elcampello.es | CMS propio (Tres Tristes Tigres, PHP) |
| Territorio y Vivienda | https://www.elcampello.es/index.php?s=areas&id=18 | Urbanismo, PGOU, visor parcela |
| Planeamiento | https://www.elcampello.es/index.php?s=areas&id=37 | Noticias IP, modificaciones, PMUS |
| Disciplina Urbanística | https://www.elcampello.es/index.php?s=areas&id=35 | Ordenanzas, licencias, modelos |
| Gestión Urbanística | https://www.elcampello.es/index.php?s=areas&id=58 | Programas actuación, reparcelaciones |
| Documentos área | `index.php?s=area_documentos&id={18,35}` | PDFs trámites y criterios interpretativos |
| Noticias área | `index.php?s=area_noticias&id={18,35,37,58}` | ~10 noticias/área con titulo+fecha+PDFs |
| Fondos urbanismo | http://fondos.elcampello.es/urbanismo/ | Repositorio PGOU/catálogo/planeamiento (403/reset en CI) |
| Sede electrónica | https://elcampello.sedelectronica.es | espublico gestiona (Gestiona) |
| Tablón anuncios | https://elcampello.sedelectronica.es/board/ | Edictos y anuncios (HTML tabla) |
| Carpeta electrónica | sede → expedientes | Requiere identificación; sin listado público |

## Cómo se listan expedientes / proyectos

1. **Noticias por área municipal** — HTML estático con `dt.fecha`, `dt.titulo`, PDFs en `/upload/noticias_ficheros/`. Incluye información pública, modificaciones PGOU, PMUS, consultas previas, expropiaciones, etc.
2. **Tablón sede** — Tabla espublico con columnas documento, expediente, procedimiento, categoría, descripción, fecha. Categoría `Urbanismo` y procedimientos como «Certificados o Informes Urbanísticos».
3. **Fondos.elcampello.es** — Apache directory listing con PDFs de planeamiento (PGOU 1986, catálogo, instrumentos en tramitación). Bloqueado desde entorno CI (403/connection reset).
4. **Sede expedientes** — Solo consulta autenticada del interesado (manual Gestiona PDF).

## Cómo se publican licencias

- **Tablón sede:** edictos de licencias/actividad cuando se publican (pocos en curso; mayoría decretos administrativos).
- **Noticias:** comunicados sobre concesión/suspensión de licencias (p. ej. vivienda turística).
- **Sin dataset histórico:** no hay listado CSV/API de licencias concedidas; trámites vía sede (certificado compatibilidad, obra mayor, DR).
- **Adapter:** tablón filtrado + páginas informativas de trámites (como Cómpeta/Pozuelo) + noticias con patrón licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor ArcGIS «Mapa Información Urbanística de Parcela Catastral»: https://gis.elcampello.es/arcgis/apps/webappviewer/index.html?id=32bcf49ed7564eccb14baf34db601d5c
  - Certificado GeoNet Territorial (*.geonet.es); REST `https://gis.elcampello.es/arcgis/rest/services` no accesible desde CI (certificado hostname mismatch + connection reset).
  - Fondos urbanismo incluye documentación gráfica PGOU (PDFs, no GeoJSON enlazable a expediente).
- **Estrategia:** documentar visor; adapter intenta REST ArcGIS con `insecure_ssl` y deja `geom_geojson` vacío si falla. Geocode del orquestador usa centroide municipio + jitter.
- **Limitaciones:** sin WFS/REST público estable desde CI; parcela catastral requiere visor interactivo; fondos.elcampello.es bloqueado; expedientes sede sin geometría.

## Limitaciones

- `fondos.elcampello.es` y `gis.elcampello.es` inaccesibles o con SSL incorrecto desde CI.
- Sede `info.0` redirige en bucle; tablón `/board/` sí responde con `insecure_ssl`.
- Tablón muestra solo ~10 anuncios recientes (sin paginación pública).
- Noticias: ~10 por área en portada (sin paginador funcional detectado).

## Adapter implementado

- `municipio/adapters/el_campello.py` — `ElCampelloAyuntamientoAdapter`
- Fuentes: noticias áreas 18/35/37/58 + tablón sede + trámites informativos web
