# Posadas, Córdoba — INE 14053

Investigación y extracción real: 9 de noviembre de 2026. Se trata del municipio
andaluz, no de la ciudad argentina homónima.

## Fuentes oficiales y alcance

- Inventario municipal: https://posadas.es/ayuntamiento/normativa-y-documentos/
- Entrada municipal de Urbanismo: https://posadas.es/ciudadania/urbanismo/
  La consulta del índice público identifica el enlace al PGOU y un modelo de
  declaración responsable; este modelo no acredita ninguna licencia concedida.

La fuente operativa es el inventario de «Normativa y Documentos». El HTML servido
contiene íntegramente el desplegable «Documentos PGOU» y las secciones de vivienda,
movilidad y equipamientos deportivos. No se observó paginación en este inventario;
el parser rechaza controles de paginación reconocibles para evitar un resultado
silenciosamente incompleto. No se recorren noticias, contratos ni formularios.

La extracción en vivo produjo **10 instrumentos con 76 enlaces documentales**:
PGOU, tres modificaciones puntuales, estudio de detalle de rehabilitación y
ampliación del Ayuntamiento, planes parciales R-9 y R-2, plan de vivienda y suelo,
plan de movilidad y plan local de instalaciones y equipamientos deportivos.
Las dos partes del plan de movilidad forman un solo registro. Los planos de
infraestructuras, normas, memorias y documentos ambientales del PGOU forman un
solo instrumento, sin presentarlos como obras independientes.

## Anuncios comprobados y agrupación

Los siguientes PDF municipales se descargan y se leen con `pdftotext -layout`
(disponible en el entorno; sin instalar dependencias). El parser exige nombre del
municipio, objeto de modificación, expediente GEX, acuerdo de aprobación inicial
y fecha del boletín. Los títulos y fechas se extraen del documento descargado:

- https://posadas.es/wp-content/uploads/2026/02/ANUNCIO-PUBLICADO-EN-EL-BOP-A-2026-326.pdf
  GEX 9445/2025, eliminación de AA-3 «La Estación» y recalificación a Manzana
  Cerrada. Acuerdo: 2026-01-29; publicación BOP: 2026-02-10.
- https://posadas.es/wp-content/uploads/2024/10/ANUNCIO-PUBLICADO-EN-EL-BOP-A-2024-3892.pdf
  GEX 4051/2024, ajuste de ordenanzas del PGOU. Acuerdo: 2024-09-26;
  publicación BOP: 2024-10-15.
- https://posadas.es/wp-content/uploads/2024/10/ANUNCIO-PUBLICADO-EN-EL-BOP-A-2024-3896.pdf
  GEX 7873/2024, calificación parcial de equipamiento en Plaza Mayor 2, Rivero
  de Posadas. Acuerdo: 2024-09-26; publicación BOP: 2024-10-15.

Cada anuncio se agrupa con su documento técnico inmediatamente siguiente y,
para los dos expedientes de 2024, con su enlace repetido de nombre descriptivo.
La asociación de esos enlaces se comprobó en la investigación descargando los
PDF técnicos: los de normas tienen contenido idéntico; los de equipamiento son
versiones del mismo objeto. El documento técnico de 2026 identifica además
expresamente GEX 2025/9445 y La Estación. No se crean registros de contratación.

`fecha_publicacion` significa publicación en el BOP, no subida al CMS. La fecha
de firma del alcalde tampoco se confunde con el acuerdo del Pleno. Para los
otros instrumentos no se asignan fechas o fases a partir de nombres de fichero,
años de directorios o expresiones genéricas de aprobación. La fase de los tres
anuncios representa el acto documentado, sin afirmar que sea la última fase actual.

## Límites expresos

Cobertura parcial del inventario actual, sin garantía de exhaustividad histórica
ni de vigencia jurídica. No hay licencias concedidas ni coordenadas verificadas.
`licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing` están desactivados;
todos los registros llevan `publication_ready: false` y geometría no disponible.

Se excluyen convenios urbanísticos, estatutos y aprobaciones de juntas de
compensación, el libro de registro como agregado, hitos de la modificación del
colegio Jesús y documentos antiguos con prefijo 1405301 que requieren resolver
su identidad. También se excluye una carpeta de Drive titulada genéricamente
«Aprobación Inicial de la modificación puntual del PGOU», sin objeto inequívoco,
y los planes sociales, turísticos o estratégicos ajenos al alcance seleccionado.
Los documentos sin fecha inequívoca no reciben fechas inventadas.

Los otros PDF se conservan con su título y enlace de procedencia, sin afirmar que
se haya comprobado su contenido ni disponibilidad. Se corrige únicamente el
atributo HTML roto que incorpora ` title=` a la URL de Ordenación Completa Hoja 1;
la parte PDF existe literalmente en el HTML fuente. No se infiere geometría de
los mapas. La primera solicitud HTTP sin User-Agent recibió 403; la extracción
real con User-Agent explícito obtuvo el HTML y los anuncios, sin credenciales.

## Reproducción y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_posadas -v` — cuatro pruebas correctas.
Cubren semántica de fechas, rechazo de documentos incorrectos o incompletos,
agrupación, exclusión de modelos, paginación, estructura rota, identidad municipal,
resolución del manifest y sustitución idempotente de instantáneas.

Extracción real con `load_manifest('posadas')`, `load_portal_adapter(manifest)` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`; configuración local
`capture_dir='evidence'`. La envoltura compartida aplica la política de entidades.
`update_proyectos` vuelve a leer el inventario completo; no existe cursor temporal
fiable para un inventario documental editable.

Evidencias sin incorporar al código: `evidence/proyectos.jsonl`,
`evidence/validation.json`, HTML de la fuente, tres anuncios BOP y capturas de
PDF técnicos usados durante la investigación. La validación contiene el número
real de registros, todas las URLs fuente y limitaciones. Sin base de datos,
publicación, despliegue, instalación ni modificación de fuentes compartidas.
