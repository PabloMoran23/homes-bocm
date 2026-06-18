# Alcalá de Henares — investigación portal ayuntamiento

## Resumen

| Fuente | URL | Formato | Uso |
|--------|-----|---------|-----|
| Portal Urbanismo | https://urbanismo.ayto-alcaladehenares.es | WordPress (Divi) + REST API | **Principal** — posts de planeamiento, convenios, licencias |
| Sede electrónica tablón | https://sede.ayto-alcaladehenares.es/web/guest/tablon-de-anuncios | STA (Liferay), carga AJAX | Secundario — sin dataset JSON embebido (a diferencia de Getafe) |
| Proyectos Urbanos | https://proyectosurbanos.ayto-alcaladehenares.es | WordPress | Infraestructuras municipales, no expedientes IP |
| PGOU | https://pgou.ayto-alcaladehenares.es | WordPress | Revisión PGOU, documentación estática |
| Transparencia | http://transparencia.ayto-alcaladehenares.es | Portal aparte | No usado en v1 |

## Licencias

- Publicadas como **posts** en el subportal de Urbanismo, categoría `licencias-urbanisticas-y-de-actividades-blog` (id 147).
- También edictos de autorización demanial, comunicaciones previas y trámites en el feed general (~24 entradas con keywords de licencia sobre 322 posts).
- **No hay** listado georreferenciado de concesiones (sin lat/lon como Madrid capital).
- Páginas informativas de trámites: `/licencias-urbanisticas-y-de-actividades`.

## Proyectos / expedientes

- **REST API** `https://urbanismo.ayto-alcaladehenares.es/wp-json/wp/v2/posts` — 322 posts, ~189 con keywords de planeamiento.
- Categorías relevantes: `convenios-urbanisticos-blog` (134), `planeamiento-y-gestion-urbanistica` (145), `documentos-de-planeamiento-y-gestion-en-tramitacion` (154), `destacados` (128).
- Contenido: aprobaciones de planes parciales/especiales, modificaciones PGOU, convenios urbanísticos, unidades de ejecución, información pública.
- PDFs enlazados en `content.rendered` de cada post.

## Limitaciones

- Certificado SSL del dominio `*.ayto-alcaladehenares.es` no verifica en cadena estándar → `insecure_ssl: true`.
- Tablón sede STA requiere POST AJAX (`submitAjax.aa`); no replicado en v1 (WP API cubre paridad).
- Sin coordenadas en licencias; `distrito`/`lat`/`lon` quedan `null`.
- Posts duplicados ocasionales (misma autorización republicada); IDs estables por URL del post.

## Adapter implementado

- Módulo: `municipio.adapters.alcala_de_henares:AlcalaDeHenaresAyuntamientoAdapter`
- Estrategia: paginar WP REST API + filtro regex (estilo Getafe/Móstoles) + extracción PDF.
