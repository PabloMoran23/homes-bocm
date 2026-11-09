# Santa Cruz del Retamar — INE 45157, Toledo

Investigación y extracción en vivo: 9 de noviembre de 2026. Se revisaron primero
`municipio/manifest.py`, el contrato `municipio/adapters/portal.py`, el cargador
de adaptadores y los ejemplos de Chipiona y Hernani. No se cambian fuentes
compartidas ni dependencias.

## Fuentes oficiales descubiertas

- [Web municipal](https://santacruzdelretamar.es/): enlaza el inventario de
  Urbanismo. Contiene además selección de personal, anuncios de contratación,
  un anteproyecto de explotación del servicio de agua y exposición pública de
  una instalación fotovoltaica. No se transforman esos anuncios en obras,
  licencias concedidas o proyectos aprobados.
- [Urbanismo](https://santacruzdelretamar.es/Urbanismo/Urbanismo.html): fuente
  implementada. Su bloque `PLAN DE ORDENACION MUNICIPAL`, hasta `NOTAS:`,
  contiene ocho enlaces documentales. La página es estática, sin paginación
  observada. El parser rechaza paginación detectada en el inventario en vez de
  devolver la primera página silenciosamente.
- [Sede electrónica](https://santacruzdelretamar.sedelectronica.es/info.0):
  contiene enlaces al tablón, transparencia y catálogo de trámites. El trámite
  de solicitud de licencia no constituye un registro de concesiones. Es una
  fuente de descubrimiento, no una fuente extraída por este adaptador.

## Unidad de extracción y procedencia documental

El resultado vivo es **un instrumento de planeamiento**, el POM, con sus ocho
documentos agrupados; no ocho proyectos independientes:

1. [Edicto DOCM](https://santacruzdelretamar.es/Urbanismo/pomdocm.pdf).
2. [Publicación BOP Toledo](https://santacruzdelretamar.es/Urbanismo/pombop.pdf).
3. [Planos comprimidos](https://santacruzdelretamar.es/Urbanismo/ordenacion.rar).
4. [Normas](https://santacruzdelretamar.es/Urbanismo/NORMASpom.pdf).
5. [Memoria](https://santacruzdelretamar.es/Urbanismo/MEMORIA.pdf).
6. [Catálogo de bienes protegidos](https://santacruzdelretamar.es/Urbanismo/CATALOGOBIENESPROTEGIDOS.pdf).
7. [Cuadro de zonas de ordenanza](https://santacruzdelretamar.es/Urbanismo/CUADRORESUMENZONASDEORDENANZA.pdf).
8. [Fichero de planeamiento](https://santacruzdelretamar.es/Urbanismo/FICHEROPLANEAMIENTO.pdf).

El título y todos los documentos se leen del HTML, sin precargar una lista de
expedientes. Se mantienen las etiquetas municipales y la URL de procedencia de
cada documento. Se resuelven enlaces relativos y eliminan únicamente fragmentos
de visualización PDF; enlaces repetidos se agrupan. Los ocho destinos dieron
HTTP 200 y firma PDF o RAR válida durante la ejecución del adaptador.

Los tres formularios urbanísticos posteriores al bloque del POM quedan fuera,
al igual que los dos documentos de bases reguladoras DOT1: estas bases no se
presentan como una aprobación del PAU ni como proyecto físico. No se recorren
enlaces de navegación ni se mezclan documentos de instrumentos diferentes.

## Fechas, alcance y límites

La lectura de los PDF de evidencia confirma que se trata de un instrumento
real: el DOCM identifica el expediente **87/06 PL**, acuerdo de la Comisión
Provincial de **31 de enero de 2013**, anuncio firmado el **21 de febrero de
2013** y publicación DOCM número **47 de 7 de marzo de 2013**. El BOP número
**72 de 30 de marzo de 2013** publica las normas. Son fechas distintas y ninguna
es la fecha de publicación de la página HTML. El BOP cita el DOCM como número
45, discrepancia frente al encabezamiento 47 del documento DOCM conservado.

El scraper no analiza el contenido PDF para extraer fechas: los registros omiten
`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y fase. Estas fechas
históricas se documentan aquí para justificar la identidad del instrumento, sin
codificarlas como constantes ni atribuir actualidad a su aprobación. El DOCM
incluye condiciones relativas a publicación, adaptación e informes sectoriales;
la presencia de los documentos en la web no acredita por sí sola vigencia actual.

Cobertura deliberadamente parcial: bloque del POM actualmente publicado en la
sección municipal de Urbanismo. No es un histórico de modificaciones, registro
de licencias, catálogo completo de obras ni un rastreo del tablón o de actas.
No se extraen coordenadas ni geometrías de los planos; tampoco se inventan.
`publication_ready=false`, `geometry_status=unavailable`. El manifiesto deja
desactivados licencias, programación y jitter. La política compartida aplicada
por el cargador devuelve este instrumento como entidad pendiente, no elegible
para actividad: la extracción no equivale a autorización para publicar.

La ausencia del bloque, del delimitador o de componentes esenciales, una
paginación detectada, un fallo HTTP o una firma documental inválida provoca
error antes de sustituir el JSONL anterior. `update_proyectos` vuelve a obtener
la instantánea completa de este mismo ámbito; no simula un incremental por fecha.

## Validación reproducible y evidencia local

Runtime utilizado, sin instalar software:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_santa_cruz_del_retamar -v`, **8 correctas**.
Cubren agrupación, procedencia, exclusiones, ausencia de metadatos inventados,
deduplicación, estructura incompleta, paginación, orígenes externos, validación
documental, preservación de la instantánea ante fallos, actualización y manifiesto.

Extracción real mediante `load_manifest('santa-cruz-del-retamar')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`;
se pasó `portal.config['evidence_dir']` apuntando al directorio local de evidencia.
Resultado: **1 registro, 8 documentos comprobados**.

`evidence/validation.json` conserva recuento vivo, URLs, limitaciones y resultado
del cargador. `evidence/urbanismo.html`, `inicio.html` y `sede.html` conservan las
páginas consultadas. `document_checks.json` y ocho archivos `.prefix` conservan
estado HTTP y los primeros 512 bytes de cada documento (no los planos completos).
Los dos edictos se descargaron completos adicionalmente como `pomdocm.pdf` y
`pombop.pdf`; `pdftotext` generó `pomdocm.txt` y `pombop-page1.txt` para la revisión
de identidad y fechas. Evidencia local, excluida del conjunto de fuentes.

No se ejecutó publicación, acceso a bases de datos ni despliegue.
