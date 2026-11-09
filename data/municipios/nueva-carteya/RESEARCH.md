# Nueva Carteya — Córdoba — INE 14046

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales descubiertas

La [portada del Ayuntamiento](https://aytonuevacarteya.es/) se identifica como web oficial y enlaza el archivo de noticias, Urbanismo y la sede electrónica de Eprinsa para Nueva Carteya. No se ha usado la sede como fuente de registros ni se afirma haber auditado todo su contenido.

La [página de Urbanismo](https://aytonuevacarteya.es/noticias/341-urbanismo.html) solo contiene enlaces a comunicación previa y declaraciones responsables en blanco. El epígrafe «NORMAS URBANÍSTICAS» no ofrece documentos enlazados. Estos formularios no acreditan licencias concedidas y se excluyen; `licencias.enabled=false`. El enlace de portada rotulado como transparencia lleva actualmente a un calendario de actividades (`/component/content/article.html?id=6&Itemid=152`), no a un inventario urbanístico utilizable.

La fuente implementada es el [archivo municipal de noticias](https://aytonuevacarteya.es/noticias.html). En la ejecución viva se recorrieron **24 páginas**, offsets 0, 8, …, 184, con 187 encabezados de artículos. Se siguen todos los enlaces de paginación del inventario hasta agotar la cola, incluidos los enlaces a última página. No hay un corte por número de registros. Páginas repetidas, estructuras vacías, enlaces ajenos al inventario, errores HTTP o superar el límite de seguridad de 500 páginas provocan error antes de sustituir el fichero de resultados. La navegación anterior/siguiente de cada noticia no se confunde con paginación del archivo.

## Registros y selección

Resultado: **2 obras físicas reales**, no expedientes de licencia ni instrumentos de planeamiento:

- [Parque Uruñuela](https://aytonuevacarteya.es/noticias/339-inauguraci%C3%B3n-del-parque-uru%C3%B1uela.html): el Ayuntamiento confirma que tuvo lugar la inauguración, que se dota a la localidad de un nuevo espacio verde y que se instaló una zona de juegos. Se conservan cuatro enlaces a fotografías municipales.
- [Gimnasio Municipal](https://aytonuevacarteya.es/noticias/340-inauguraci%C3%B3n-gimnasio-municipal.html): confirma la inauguración oficial de una nueva instalación en el Polideportivo Municipal de San Pedro, de cerca de 1.000 m². Se conservan ocho enlaces a fotografías municipales.

El selector exige un título de inauguración de equipamiento físico y una confirmación textual «tuvo lugar la inauguración» en la noticia completa. El registro se genera con el título y descripción extraídos, nunca con una ficha literal precargada. La [inauguración del nuevo Ayuntamiento](https://aytonuevacarteya.es/noticias/19-noticias/noticias-generales/75-inauguraci%C3%B3n-nuevo-ayuntamiento-de-nueva-carteya.html) se revisó pero se excluyó: su texto solo invita a una inauguración futura. También se excluyen programas de ayudas, convenios sociales, licitaciones, actividades y la publicación «actuaciones feader», que presenta una imagen sin descripción textual verificable de la obra.

Cada actuación agrupa su noticia de procedencia, los eventuales PDF enlazados y sus imágenes. Los enlaces duplicados se eliminan dentro de la actuación, sin crear registros independientes por fotografía o documento. En estas dos noticias no hay PDF técnicos enlazados. No se afirma disponer de proyectos técnicos, resoluciones, inventario de planeamiento ni expediente administrativo completo.

## Fechas, límites y procedencia

Los actos se mencionan como «16 de abril» y «martes 24 de junio», sin año explícito en el texto. No se deduce un año por carpetas de imágenes, calendario o día de la semana. No se emite fecha normalizada de publicación, acuerdo, aprobación o inauguración. La descripción conserva las menciones originales; una inauguración no equivale a un acuerdo de aprobación.

Cobertura **parcial y conservadora** de obras ya inauguradas comunicadas en el archivo público actual; no es censo de todas las obras o proyectos del municipio. El recorrido completo del archivo no implica selección de todas las obras que pudieran mencionarse en títulos ambiguos, imágenes o noticias no clasificadas como inauguración. No se ha establecido vigencia administrativa ni disponibilidad actual de los equipamientos. No se inventan coordenadas, direcciones precisas ni geometrías. Se emiten `geometry_status=unavailable` y `publication_ready=false`; programación y jitter están desactivados.

## Validación reproducible

Runtime autorizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_nueva_carteya -v` — **5 pruebas correctas**. Cubren exclusión de formularios y noticias ajenas, invitaciones sin confirmación, documentos agrupados, ausencia de fechas/coordenadas inventadas, paginación no consecutiva y fallo sin sustituir resultados cuando el servidor repite páginas.

Ejecución real mediante `load_manifest('nueva-carteya')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['capture_dir']='evidence/captures'`. Recorrió 24 páginas y consultó tres noticias candidatas, produciendo dos registros. La anotación compartida de entidades informa dos categorías desconocidas; no se fuerza una clasificación especializada.

Evidencia local, sin publicación: `evidence/proyectos.jsonl`, `evidence/validation.json` (recuento, hora UTC de extracción, URLs completas y limitaciones). `evidence/captures/` contiene los cuerpos HTML recibidos por el adaptador; cada nombre es los primeros 16 caracteres SHA-256 de su URL UTF-8 más `.html`. Otras capturas exploratorias están en `evidence/`. Los enlaces a fotografías se conservan, sin descargar esos binarios. La evidencia no forma parte de los cuatro archivos fuente entregados.
