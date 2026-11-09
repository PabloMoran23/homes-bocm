# Firgas — INE 35008, Las Palmas, Canarias

Consulta y extracción real: 8 de noviembre de 2026. Adaptador limitado a un municipio.

## Fuentes oficiales descubiertas

- Inventario municipal actual: https://www.villadefirgas.es/urbanismo/ . La página de Oficina Técnica y Urbanismo publica NNSS, archivos, revisiones/modificaciones y planes parciales, además de otra sección PGO. Se consulta el HTML vivo; no se precargan expedientes ni se convierten enlaces genéricos en proyectos.
- Archivo autonómico: https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/pages/consulta/islaMunicipio.jsp?municipio=8&provincia=35 . Respuesta HTTP 200, municipio FIRGAS: un instrumento de planeamiento general y cero de desarrollo. Consultado como descubrimiento, no extraído como registro ni utilizado para confirmar vigencia. Sus categorías no equivalen al inventario histórico municipal.
- La búsqueda también localizó el portal municipal antiguo `www.ciudadano.firgas.es`; la web actual enlaza contenidos antiguos. No se usa como fuente adicional ni se mezclan sus versiones.

## Cobertura y agrupación

Nueve instrumentos reales extraídos de la sección NNSS del inventario municipal:

1. Normas Subsidiarias de Planeamiento del Municipio de Firgas: un registro con 30 enlaces (memoria, normativa, planos, cuatro partes del catálogo etnográfico y publicaciones). Los planos y las fichas no se convierten en proyectos independientes.
2. Avance de revisión parcial de las NNSS, Parque Industrial Las Huertecillas.
3. Modificación puntual de las NNSS, cambio de trazado de dos vías, aprobación inicial.
4. Plan Parcial SAU 3 Mesetas de Casablanca.
5. Plan Parcial SAU 6 Cambalud Sur.
6. Plan Parcial SAU 4 La Cruz.
7. Plan Parcial Cambalud Norte.
8. Plan Parcial SAU 5 Los Dolores.
9. Plan Parcial SAU 2 Cambalud Centro.

La sección seleccionada está completa en el HTML, con todas las filas de sus tablas; no se aplica límite de registros. No hay paginación del inventario observada. Los enlaces del calendario y noticias exteriores son ajenos a la sección. Si aparece paginación dentro del inventario, el adaptador falla expresamente hasta poder implementar su recorrido, sin escribir una extracción parcial. También falla si desaparecen secciones, cambian las columnas, hay filas malformadas o instrumentos duplicados.

Se excluye la sección PGO: contiene fases históricas de avance y aprobación inicial, una declaración de caducidad de 2012 y referencias a un avance supletorio. No se adjudica a ese conjunto una fase actual. Tampoco se extraen como proyectos las categorías de suelo, sectores o asentamientos descritos en las determinaciones de las NNSS. No se pretende cobertura de toda la obra pública ni de todo el archivo de planeamiento. Formularios de solicitud, licitaciones y noticias quedan fuera; no se ha verificado registro público de licencias concedidas.

## Fechas y procedencia

Las NNSS conservan dos eventos: aprobación definitiva parcial de 08/06/1999, publicada en BOC 06/10/1999; aprobación definitiva de 09/04/2001, publicada en BOC 12/11/2001 y BOP 14/12/2001. Se retienen ambas publicaciones del segundo evento y sus enlaces, sin elegir una arbitrariamente como fecha general.

Las tablas separan fase, fecha de aprobación, acuerdo plenario, acuerdo COTMAC y publicaciones BOC/BOP. Las revisiones/modificaciones usan `fecha_acuerdo`, nunca una fecha inferida de aprobación definitiva. `columnas_fuente` conserva los valores literales. `publicaciones` mantiene todos los boletines; `documentos` todos los enlaces por instrumento y su `source_url`. Cambalud Norte cita BOP 149 de 30/11/1990 sin enlace: `url: null` y procedencia municipal, sin construir una URL supuesta.

Todas las fechas proceden del inventario, sin cotejo individual de cada boletín. Los enlaces históricos HTTP se conservan tal como se publican, aunque algunos destinos puedan haber cambiado o desaparecido. No se infiere publicación de las fechas de subida de WordPress. No se verifica vigencia jurídica actual, y `vigencia_verificada: false` lo declara incluso cuando la página llama a las NNSS vigentes. No hay coordenadas ni geometría deducida; `publication_ready: false`. Manifest: licencias y programación desactivadas, jitter desactivado.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_firgas -v`, siete correctas. Cubren agrupación documental y aislamiento entre instrumentos/PGO, fechas y publicaciones múltiples, boletín sin enlace, rechazo de cambios estructurales/paginación, actualización por instantánea y licencias desactivadas. Los fixtures son HTML mínimo independiente, sin depender de evidencias locales.

Extracción real mediante `load_manifest('firgas')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir='evidence'` en la configuración de esa ejecución. Resultado: nueve registros, política de entidades `status: ok`; clasificación de uso desconocida para nueve instrumentos (no se infiere uso residencial de sus títulos). La actualización regenera una instantánea completa, sin cursor ni pretensión de histórico incremental.

Evidencias locales, no destinadas a commit:

- `evidence/proyectos.jsonl`: registros reales del adaptador cargado desde el manifest.
- `evidence/validation.json`: `live_records: 9`, URLs, resultado y limitaciones.
- `evidence/urbanismo.html`: captura de la respuesta usada por el adaptador.
- `evidence/archivo-canarias.html`: captura del inventario autonómico consultado.
- `evidence/memoria_nnss.pdf`: memoria municipal descargada desde https://www.villadefirgas.es/wp-content/uploads/2021/06/01-memoria_nnss.pdf , HTTP 200, `application/pdf`, firma `%PDF-`, 3.277.602 bytes. Esto comprueba ese documento; no implica que todos los destinos enlazados se hayan descargado o validado.

No se realizan publicación, geocodificación, acceso a bases de datos o despliegues.
