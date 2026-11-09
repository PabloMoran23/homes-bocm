# La Puebla de Montalbán — Toledo — INE 45136

Investigación y extracción real: 8 de noviembre de 2026. Adaptador único, sin cambios compartidos ni dependencias nuevas.

## Fuentes oficiales descubiertas

- Ayuntamiento: https://www.pueblademontalban.com
- Inventario público de publicaciones WordPress: https://www.pueblademontalban.com/wp-json/wp/v2/posts?search=%22plan%20de%20ordenaci%C3%B3n%20municipal%22&per_page=100&page=1
- Sede y portal de transparencia: https://lapueblademontalban.sedelectronica.es/transparency . La categoría «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» anuncia 115 documentos. La navegación depende de callbacks Wicket de sesión; las peticiones anónimas probadas devolvieron cuerpo vacío. No se afirma haber recorrido esos 115 documentos ni se reutilizan tokens temporales en el adaptador.
- Ordenanzas: https://www.pueblademontalban.com/540-2 . Inventario mixto de normas fiscales y administrativas, con adaptación de NNSS al CTE. No se convierte ese listado en proyectos, obras ni licencias.
- Oficina virtual: https://www.pueblademontalban.com/oficina-virtual . Las solicitudes de obra mayor son formularios, no concesiones; licencias desactivadas.
- La búsqueda oficial también localizó la modificación puntual 7 de las NNSS en BOP Toledo (https://bop.diputoledo.es/webEbop/DocGet?id=25041861%3B0&insert_number=1747&insert_year=2025) y documentación regional (https://urbanismo.castillalamancha.es/sites/default/files/expedientes/cci_toledo_modificacion_puntual_no_7_de_las_nnss_de_la_puebla_de_montalban.pdf). Son fuentes adicionales descubiertas, no inventarios recorridos ni registros incluidos en esta cobertura. El adaptador no pretende abarcar todas las NNSS o actuaciones del municipio.

## Cobertura implementada y procedencia

**Un instrumento real: el Plan de Ordenación Municipal (POM)**. Se consulta en vivo la API pública de publicaciones del ayuntamiento con la consulta indicada. La respuesta observada contiene cinco publicaciones en una página (`X-WP-Total: 5`, `X-WP-TotalPages: 1`). Se agrupan tres referencias del mismo POM en `documentos`, conservando URL pública, URL individual API, título, descripción, fecha de publicación y enlaces expresos del cuerpo:

1. Información pública del POM, publicada el 05/03/2020: https://www.pueblademontalban.com/inicio-del-periodo-de-informacion-publica-del-plan-de-ordenacion-municipal.html . Identifica el documento técnico depositado en Urbanismo y disponible en sede; no contiene un enlace directo al expediente técnico. No se convierte su fecha de publicación en fecha de acuerdo.
2. Acuerdo del Pleno de **19/05/2023**, publicado el **20/05/2023**: https://www.pueblademontalban.com/informacion-municipal-aprobacion-del-plan-de-ordenacion-municipal-pom-de-la-puebla-de-montalban.html . El propio texto indica su remisión a la Consejería para aprobación definitiva. Por tanto `fecha_acuerdo=2023-05-19`, `fecha_publicacion=2023-05-20`, `fecha_aprob=null`. La fecha 09/05/2023 se refiere al informe ambiental publicado en DOCM y no se usa como fecha de aprobación del POM.
3. Seguimiento publicado el 19/03/2024: https://www.pueblademontalban.com/el-ayuntamiento-de-la-puebla-de-montalban-plantea-sus-necesidades-y-problemas-a-la-confederacion-hidrografica-del-tajo.html . Menciona información pendiente de CHT para continuar los trámites del POM; se conserva como contexto del instrumento, sin crear una obra a partir de esa reunión ni sustituir el acuerdo de 2023.

Las otras dos coincidencias, firma de contrato de redacción de 2017 y reunión de 2015, se excluyen: no acreditan un instrumento adicional. El registro es una síntesis documental del POM identificado, no una licencia, un anuncio de contratación transformado en proyecto ni una afirmación de aprobación definitiva. La fuente es comunicación municipal, no el acta original ni el expediente técnico descargado. No se acredita vigencia actual. `fecha_ultima_publicacion_fuente` conserva la referencia de 2024 separadamente.

Cobertura deliberadamente parcial del POM, no de todas las obras, instrumentos, licencias o publicaciones municipales. Coordenadas y geometría nulas; `publication_ready=false`. Sin geocodificación artificial ni ejecución programada.

## Comportamiento y comprobaciones

El adaptador sigue todas las páginas declaradas por la API, sin límite silencioso. Comprueba total de publicaciones, estabilidad de cabeceras durante el recorrido, identificadores repetidos y dominio de procedencia. Cabeceras ausentes, fuente vacía, cambio de estructura o ausencia de publicaciones sustantivas del POM provocan error antes de escribir resultados. Las actualizaciones son instantáneas completas del mismo ámbito, sin filtrar documentos históricos. No se fija un ID de publicación para emitir un registro precargado: los datos y fechas se extraen del contenido vivo.

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_la_puebla_de_montalban -v` — **7 correctas**. Verifican agrupación, separación de fechas, contexto sin nuevos proyectos, exclusión de formularios/contratos/reuniones, rechazo de fuente ajena o acuerdo sin fecha y paginación completa con detección de repeticiones y cambios.

Extracción real mediante `load_manifest`, `load_portal_adapter` y `backfill_proyectos`, con anotación de política de entidades del registro compartido: **1 registro**, cinco publicaciones inspeccionadas, tres referencias retenidas. La política clasifica la categoría como desconocida; no se fuerza una categoría ni publicación automática.

Evidencia local (no forma parte de los cuatro archivos fuente): `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/posts-1.json` (respuesta completa de la extracción), páginas HTML municipales, sede y captura vacía del callback. `validation.json` contiene `live_records`, `source_urls`, limitaciones y resultado de política. No se publica ni se escribe en bases de datos.
