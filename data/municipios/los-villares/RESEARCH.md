# Los Villares (Jaén), INE 23099

Investigación y validación en vivo: 9 de noviembre de 2026.

## Fuentes oficiales y alcance

Inventario seleccionado: https://www.losvillares.com/ayuntamiento/urbanismo/

La página oficial de Urbanismo publica tablas de documentos de tres instrumentos concretos. Los encabezados de los boletines descargados identifican expresamente al Ayuntamiento de Los Villares (Jaén), evitando confundirlo con Los Villares de Soria, Villares de la Reina o la pedanía de Andújar. El inventario se sirve completo en una página, sin controles de paginación observados. El adaptador rechaza paginación nueva, contenedores ausentes, secciones desconocidas y documentos inesperados, sin entregar una primera página truncada.

Se descubrió también la sede oficial https://losvillares.sedelectronica.es/info.0, que ofrece trámites, transparencia y un tablón general. No se usa ese catálogo de trámites ni las convocatorias o anuncios presupuestarios como proyectos. La búsqueda descubrió documentación antigua del PGOU en https://losvillares.com/wp-content/uploads/urbanismo/pgmou2011/PROG%2BEEF.pdf, pero no forma parte del inventario actual seleccionado: no se añade como expediente sintético ni se afirma cobertura de ese archivo histórico. La cobertura es parcial respecto del municipio, completa respecto de las tres tablas actuales de instrumentos de esta página; no constituye catálogo completo de planeamiento vigente, obras públicas o expedientes históricos.

## Instrumentos y procedencia documental

Cada registro corresponde a una tabla y conserva todos sus documentos con el título literal y `inventory_url`. Se eliminan únicamente los enlaces duplicados de iconos. Los nombres de directorio no determinan la agrupación: los dos anuncios del estudio UAS-4 están en `innovacion/`, pero pertenecen a su tabla del estudio de detalle.

1. Modificación del art. IX.3.19 de las NNSS, superficie de venta del uso comercial: [documento técnico](https://www.losvillares.com/wp-content/uploads/urbanismo/innovacion/modificacionns.pdf) y [publicación de aprobación definitiva](https://www.losvillares.com/wp-content/uploads/urbanismo/innovacion/bop-modificacionns.pdf).
2. Modificación de NNSS de equipamientos del sector SUOI2: [documento de innovación](https://www.losvillares.com/wp-content/uploads/urbanismo/innovacion2/doc-innovacion.pdf) y [información pública en BOP](https://www.losvillares.com/wp-content/uploads/urbanismo/innovacion2/ip-bop.pdf).
3. Estudio de detalle UAS-4, calle Eliche–carretera de Martos: [documento aprobado inicialmente según su etiqueta](https://www.losvillares.com/wp-content/uploads/urbanismo/planeamiento/estudiodetallecrtmartos.pdf), [anuncio inicial](https://www.losvillares.com/wp-content/uploads/urbanismo/innovacion/anuncio-aprobacioninicial.pdf) y [anuncio definitivo](https://www.losvillares.com/wp-content/uploads/urbanismo/innovacion/anuncio-aprobaciondefinitiva.pdf).

Los siete enlaces respondieron HTTP 200, `application/pdf` y firma `%PDF`. Se guardaron completos en `evidence/`; `documents.json` conserva URL original/final, estado, tamaño, firma y ruta de captura. El PDF del estudio técnico ocupa aproximadamente 49 MB. Los cuatro anuncios BOP se convirtieron localmente a texto con el `pdftotext` preexistente para comprobar identidad, objeto y cronología. El adaptador no necesita ese programa ni vuelve a descargar los PDF en cada ejecución: extrae sus enlaces del inventario vivo. No se ha auditado el contenido técnico completo ni la vigencia jurídica actual.

## Fechas y semántica

Cronología comprobada manualmente en las copias municipales de los anuncios del BOP de Jaén:

| Documento | Acuerdo que describe | Publicación en BOP |
| --- | --- | --- |
| `innovacion/bop-modificacionns.pdf`, anuncio 2023/1072 | Aprobación definitiva: 2022-08-16 | 2023-03-17, número 52 |
| `innovacion2/ip-bop.pdf`, anuncio 2024/5861 | Aprobación inicial: 2024-11-28 | 2025-01-08, número 4 |
| `innovacion/anuncio-aprobacioninicial.pdf`, anuncio 2024/969 | Aprobación inicial del estudio UAS-4: 2024-02-21 | 2024-03-21, número 57 |
| `innovacion/anuncio-aprobaciondefinitiva.pdf`, anuncio 2024/2962 | Aprobación definitiva del estudio UAS-4: 2024-05-14 | 2024-07-10, número 134 |

Estas fechas no se precargan en el adaptador: la extracción HTML no dispone de esos campos ni implementa análisis de PDF. Los registros omiten `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase`. Las etiquetas documentales se conservan como tales; no se convierten en fase del instrumento ni en fecha de aprobación. No se deducen fechas del CMS, de las rutas o de la fecha de firma de un edicto.

La tabla «Modelos» contiene una declaración responsable/comunicación previa, que es un formulario y se excluye. No se verificó un registro público de licencias concedidas; `licencias.enabled=false` y ambos métodos de licencias generan cero registros sin acceder a la red. No se extraen noticias o licitaciones como actuaciones.

Sin coordenadas ni geometría inventadas; `geometry_status=unavailable`, `publication_ready=false`, `schedule.enabled=false` y `geocode.jitter_missing=false`. La carga mediante el registro compartido aplica su política de entidades, sin elevar estos documentos a actuaciones publicables.

## Implementación y comprobaciones

Solo se añaden el manifest, esta investigación, `municipio/adapters/los_villares.py` y `municipio/test_los_villares.py`; sin dependencias nuevas ni cambios compartidos. Identificadores deterministas por encabezado normalizado. Los documentos se agrupan por tabla; los enlaces repetidos se deduplican. Una actualización vuelve a leer el inventario completo, sin marca temporal ni límite de registros; sustituye el JSONL atómicamente después de validar toda la página.

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_los_villares -v`: **8 correctas**. Cubren aislamiento de documentos entre instrumentos, deduplicación, identidad estable, exclusión de formularios, ausencia de fechas/geometría inferidas, cambios de estructura, paginación, enlaces inesperados, resolución del manifest, actualización completa y conservación de la salida anterior ante fallos.

Extracción real: `load_portal_adapter(load_manifest('los-villares')).backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **3 registros y 7 enlaces documentales**. Se verificó que los identificadores y documentos de la extracción en vivo coinciden con la captura HTML y con las siete descargas comprobadas. Evidencia local sin publicación: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/urbanismo.html`, `evidence/documents.json`, PDF y textos de los anuncios. Los archivos de evidencia no son fuentes para el scraper ni se deben incluir en el commit.
