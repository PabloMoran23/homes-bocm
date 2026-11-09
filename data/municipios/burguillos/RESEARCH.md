# Burguillos — INE 41019, Sevilla, Andalucía

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes actuales y procedencia

1. Inventario oficial municipal del PGOU:
   https://transparencia.burguillos.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00057

   Se recorren todos los enlaces de paginación `pagegalleryfiles-1-2`, también los descubiertos en páginas sucesivas, hasta agotar la cola. En vivo: cinco páginas numeradas de diez documentos salvo la última, con ocho; **48 PDF únicos**. La URL sin consulta y `pagegalleryfiles-1-2=1` son alias comprobados. Se deduplican los documentos por URL, conservando título y página de procedencia. Todos pertenecen al mismo PGOU y forman **un registro**, no 48 proyectos independientes. Se seleccionan únicamente PDF de la tabla y galería municipal `IND-50-`.

2. Nuevo Plan Básico de Ordenación Municipal:
   https://nuevoplandeburguillos.es/

   Procedencia municipal comprobada durante cada extracción a través del enlace de la noticia oficial:
   https://www.burguillos.es/es/actualidad/noticias/NUEVO-PLAN-BASICO-DE-ORDENACION-MUNICIPAL-DEL-BURGUILLOS/

   **Seis PDF únicos** en una página estática: manual de participación, diagnóstico previo, memoria general, documentación gráfica, documento inicial estratégico y planos. Las tarjetas aparecen duplicadas en el HTML y se deduplican. Se agrupan en **un registro PBOM**. El manual es documentación auxiliar del instrumento respaldado por documentos técnicos, nunca una actuación independiente. La página incluye además un enlace vacío de un municipio distinto (Peñaflor), excluido mediante comprobación del dominio. La existencia de un manual o formulario sin memoria o documento estratégico provoca error. Se conservan los enlaces HTTP tal como se publican; la muestra técnica se verificó por HTTPS y ambas URL constan en la evidencia.

## Semántica y cobertura parcial

Se extraen exclusivamente estos dos inventarios de planeamiento. No es un censo municipal completo ni un inventario exhaustivo de obras físicas, modificaciones, expedientes históricos o concesiones de licencia. No se transforman noticias genéricas ni anuncios de contratación en proyectos. La noticia del PBOM se utiliza para comprobar la procedencia, sin generar un tercer registro.

El PGOU contiene una cronología con aprobación definitiva parcial de 2006, publicación en BOP, documento complementario de 2007, sentencia y resolución de cumplimiento posteriores. La descripción conserva los párrafos completos de la fuente. No se colapsan esos eventos en una fecha de aprobación ni se atribuye vigencia jurídica al paquete completo. No se rellenan `fecha`, `fecha_publicacion`, `fecha_acuerdo` o `fecha_aprob`: tampoco se toma la fecha de la noticia de presentación del PBOM como fecha del plan. Los directorios de subida de los PDF y la explicación genérica de las ocho fases no acreditan fechas de aprobación o estado actual.

Sin coordenadas, geometría inventada ni fase deducida. `publication_ready: false`, `geometry_status: unavailable`. Licencias desactivadas por ausencia de un registro público de concesiones verificado. `schedule.enabled: false` y `geocode.jitter_missing: false`.

## Robustez y validación

El adaptador falla ante ausencia de cabecera/documentos del PGOU, repetición de documentos en páginas distintas de la primera, errores HTTP, redirecciones de dominio inesperadas, pérdida del enlace municipal de procedencia o ausencia de documentación técnica del PBOM. El límite de seguridad de 100 páginas genera error, nunca salida truncada. Una nueva paginación convencional del PBOM exige revisión y genera error. La escritura atómica se realiza únicamente tras completar ambos inventarios. La actualización vuelve a leerlos íntegramente sin usar fechas como cursor.

Runtime utilizado, sin instalar paquetes:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`

Pruebas:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_burguillos -v`

Resultado: **cinco pruebas correctas**. Comprueban selección y procedencia de documentos, deduplicación, descubrimiento de una tercera página desde la segunda, agrupación en dos instrumentos, rechazo de páginas repetidas/formularios sin soporte técnico, ausencia de fechas/coordenadas/fases inventadas y licencias desactivadas.

Extracción real mediante `BurguillosAyuntamientoAdapter.backfill_proyectos`: **2 registros, 54 documentos enlazados**. Evidencia local ignorada por git en `evidence/proyectos.jsonl` y `evidence/validation.json`; capturas de las ocho peticiones HTML en `source-01.html` a `source-08.html`, además de las capturas de investigación inicial. `validation.json` contiene URLs consultadas, recuento vivo, limitaciones, documentos por instrumento y comprobaciones PDF.

Verificación documental de una memoria por instrumento: respuesta HTTP 206, tipo `application/pdf`, firma `%PDF-` y captura de los primeros 1024 bytes. No se descargaron ni interpretaron íntegramente los 54 PDF; no se garantiza la accesibilidad individual de todos sus enlaces. Sin bases de datos, publicación, geocodificación, despliegue ni cambios en fuentes compartidas.
