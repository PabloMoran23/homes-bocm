# Olías del Rey — INE 45122, Toledo

Investigación y extracción real: 8 de noviembre de 2026. Se revisaron primero
`municipio/adapters/portal.py`, `municipio/manifest.py`, el registro dinámico de
adaptadores y los ejemplos de Manlleu y Chipiona. No se requieren cambios compartidos.

## Fuente oficial y alcance

El menú de la [web municipal](https://www.ayuntamientodeoliasdelrey.com/) enlaza
[Urbanismo y Servicios Generales](https://www.ayuntamientodeoliasdelrey.com/urbanismo/).
Esta página contiene el inventario explícito «REVISIÓN DE LAS NORMAS SUBSIDIARIAS
DE OLÍAS DEL REY (TOLEDO)»: definiciones, fichas urbanísticas, memoria, normas
urbanísticas y plano. Los cinco documentos son componentes de **un instrumento**,
no cinco proyectos. El adaptador conserva sus títulos y URL bajo `documentos` y
el enlace municipal de información adicional bajo `enlaces_relacionados`.

Los cinco archivos se descargaron completos: cuatro PDF con firma `%PDF` y un
JPEG con firma JPEG, todos HTTP 200 y tipos de contenido correspondientes.
Las URL exactas, tamaños, destinos y capturas están en
`evidence/source-checks.json`. La memoria identifica en su portada el instrumento
y el municipio; sus cabeceras dicen «Septiembre 1998» (texto extraído en
`evidence/memoria.txt`). Es una referencia del documento, **no** una fecha de
aprobación ni publicación. La carpeta web `2022/05` tampoco acredita esas fechas.
La disponibilidad actual de este inventario no demuestra vigencia ni actualización
jurídica de la revisión histórica.

La página incluye bloques de escritorio y móvil idénticos. Se deduplican por URL
y se exige que ambos paquetes coincidan. No se observó paginación en el inventario;
el parser rechaza indicadores de paginación en vez de omitir páginas. No se
recorre el archivo de noticias ni se presenta este paquete como cobertura total
del planeamiento municipal. Cualquier documento adicional dentro de la lista del
instrumento se conserva; un componente esencial ausente provoca error.

También se consultó el [enlace de transparencia publicado junto al paquete](https://oliasdelrey.sedelectronica.es/transparency/af0e3267-2c1f-4ecb-b513-7d1fbd85d535/).
Respondió HTTP 200 y mostró «2. JURIDICO Y PATRIMONIAL», sesiones del Pleno (103),
proyectos en tramitación (0), ordenanzas (34) e inventario de bienes (3).
Captura: `evidence/document-5.html`. No es un inventario adicional de proyectos
extraído por este adaptador, y su contador cero no demuestra ausencia de proyectos
en el municipio. Los modelos 311/321 y la documentación para solicitar licencias
son formularios, no concesiones: se excluyen, al igual que ordenanzas, legislación
general, incidencias y noticias ajenas al paquete. No se verificó registro público
de licencias concedidas; `licencias.enabled=false`.

## Semántica y límites

Una fila identifica la revisión publicada, sin afirmar acuerdo administrativo,
aprobación, fase o vigencia. `fecha`, `fecha_publicacion`, `fecha_acuerdo` y
`fecha_aprob` son nulas. Se conservan enlaces de procedencia por documento. No se
fabrican coordenadas ni se convierte el plano raster en geometría: latitud,
longitud y geometría nulas; `publication_ready=false`. El resultado incluye sus
limitaciones. `schedule.enabled=false` y `geocode.jitter_missing=false`.

## Validación reproducible

Runtime autorizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_olias_del_rey -v`: **8 pruebas correctas**:
  agrupación, exclusión de formularios/navegación, componentes ausentes,
  paginación, enlaces externos, duplicados contradictorios, retención de anexos
  con identidad estable y contrato de actualización/licencias desactivadas.
- Extracción en vivo mediante `load_manifest('olias-del-rey')`,
  `load_portal_adapter(...)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`:
  **1 registro real, 5 documentos**. La anotación de política compartida queda
  conservada; su clasificación es `unknown`, sin forzar elegibilidad de actividad.
- `evidence/validation.json` contiene `live_records`, `source_urls`, limitaciones,
  hora de extracción y resultado de pruebas; `evidence/urbanismo.html` conserva
  el inventario consultado. La evidencia es local y no se incorpora a fuentes.

La actualización refresca el paquete entero, sin usar fechas desconocidas como
filtro incremental. No se ejecutaron publicación, geocodificación, sincronización
ni operaciones de base de datos.
