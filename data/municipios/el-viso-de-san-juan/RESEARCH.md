# El Viso de San Juan — INE 45199, Toledo

Investigación y extracción real: 9 de noviembre de 2026. Comunidad autónoma: Castilla-La Mancha.

## Descubrimiento y fuentes oficiales

- Inventario de Urbanismo y Servicios: https://elvisodesanjuan.org/areas-municipales/urbanismo-servicios/
- Portal de Transparencia: https://elvisodesanjuan.org/ayuntamiento/portal-de-transparencia/ . Enlaza expresamente «Plan de Ordenación Municipal» al inventario anterior.
- Trámites de Obras y Urbanismo: https://elvisodesanjuan.org/gestiones-tramites/obras-urbanismo/ . Contiene requisitos y solicitudes; no se interpreta como registro de licencias concedidas.
- La antigua dirección https://www.elvisodesanjuan.es/ redirigió a https://elvisodesanjuan.org/ durante la investigación. No se mezcla documentación de El Viso (Córdoba).

La fuente municipal ofrece el Plan de Ordenación Municipal de El Viso de San Juan con 26 PDF: 15 planos de clasificación y calificación, 5 de ordenación estructural, 4 de redes/tráfico y 2 documentos principales:

- https://elvisodesanjuan.org/pdf/normas-urbanisticas.pdf
- https://elvisodesanjuan.org/pdf/fichas-resumen-ambitos-urbanisticos.pdf

Se descargaron los dos documentos principales. Sus portadas identifican el POM, El Viso de San Juan y Toledo. Las fichas se identifican como «Anexo 2 Normativa». Ambas portadas dicen «Documento noviembre 2015»: es la versión documental, no una fecha de acuerdo, aprobación ni publicación. Los 26 enlaces se conservan bajo `documentos`, con título, tipo y página de procedencia. Los planos de redes no se convierten en proyectos de obras independientes, ni las fichas de ámbitos en licencias o actuaciones ejecutadas.

## Cobertura y comportamiento

Resultado real: **1 instrumento, 26 documentos agrupados**. Es un inventario documental actual, con cobertura parcial: no constituye un catálogo completo de planeamiento, modificaciones, obras, acuerdos o historia urbanística. No se afirma vigencia jurídica, aprobación definitiva ni ejecución. No se incorporan anuncios de contratación o noticias genéricas.

No se observó paginación en el inventario completo. El parser lee todos los enlaces PDF del contenedor municipal y deduplica por URL. Si aparecen controles de paginación, documentos desconocidos, enlaces de otra procedencia, una redirección fuera de la página o faltan las normas/fichas del POM, falla explícitamente para evitar una extracción parcial silenciosa. La actualización sustituye la instantánea completa; no simula un histórico incremental.

`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` son nulos: la página no aporta esas evidencias. No se usan fechas del CMS ni de las cabeceras HTTP. Sin coordenadas ni geometría extraída de los planos; `publication_ready=false`. Licencias, programación y jitter de geocodificación desactivados. El manifest usa conexión pública directa (`trust_env: false`); no requiere sesión, credenciales ni servicios externos de persistencia.

## Verificación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_el_viso_de_san_juan -v
```

Seis pruebas satisfactorias: agrupación y procedencia de documentos, deduplicación, ausencia de fechas/coordenadas inventadas, rechazo de formularios y vacíos, paginación y documentos desconocidos, aislamiento municipal, configuración y contrato de actualización.

La ejecución real se realizó cargando el manifest con `load_manifest('el-viso-de-san-juan')`, resolviendo el adaptador con `load_portal_adapter`, añadiendo `capture_dir='evidence'` a la configuración local y llamando `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Se ejecutó así también la anotación semántica compartida del registro; no se cambió esa política.

Evidencia local, fuera de los cuatro fuentes entregables:

- `evidence/proyectos.jsonl`: registro real extraído.
- `evidence/validation.json`: recuento, URLs, resultado, pruebas, limitaciones y verificación de enlaces.
- `evidence/urbanismo.html`: captura íntegra de la extracción real; capturas adicionales de transparencia y trámites.
- `evidence/normas.pdf`, `evidence/fichas.pdf` y sus primeras páginas en texto: comprobación de identidad y versión documental.
- `evidence/document-*.prefix`: primeros bytes de cada PDF; no se descargan todos los planos completos. Los estados HTTP, destinos finales y firmas PDF se detallan en la validación.

Sin publicación, despliegue, base de datos, geocodificación ni cambios compartidos o de dependencias.
