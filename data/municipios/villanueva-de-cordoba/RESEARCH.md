# Villanueva de Córdoba — INE 14069, Córdoba, Andalucía

Verificación: 2026-11-08. Cobertura parcial del inventario municipal de planeamiento
actualmente accesible, no un censo histórico completo de proyectos o licencias.

## Descubrimiento y fuentes oficiales

La página municipal [Ordenanzas y reglamentos](https://www.villanuevadecordoba.com/w/ordenanzas-y-reglamentos/)
enlaza a [Normas urbanísticas](https://www.villanuevadecordoba.com/w/servicios/urbanismo/).
Se descargaron ambas páginas; la segunda es la fuente operativa del adaptador.
Contiene una lista estática de cinco enlaces, sin controles de paginación:

- PGOU: [normativa rectificada, BOJA 203/2015](https://www.juntadeandalucia.es/boja/2015/203/BOJA15-203-00093-16823-01_00077792.pdf).
- Avance de identificación y delimitación de asentamientos urbanísticos y ámbitos
  de hábitat rural diseminado: [BOP 952/2018](https://bop.dipucordoba.es/visor-pdf/23-03-2018/BOP-A-2018-952.pdf).
- Dos ordenanzas generales de procedimientos de obras/edificaciones: excluidas.
- Inventario toponímico: excluido; no se convierte cada topónimo en un proyecto.

El dominio municipal enlaza directamente los documentos de la Junta y de la
Diputación. El enlace BOJA publicado usa HTTP; su equivalente HTTPS fue comprobado
y es el que descarga el adaptador, conservando también la URL original.
La sección [noticias de Urbanismo](https://www.villanuevadecordoba.com/w/category/urbanismo/)
y la [sede electrónica](https://villanuevadecordoba.sedelectronica.es/info.0)
fueron identificadas durante el descubrimiento, pero no se usan como inventarios
ni se presupone que sus anuncios o trámites constituyan licencias concedidas.
No se ha recorrido su histórico ni se declara cobertura de estas fuentes.

## Qué representan los dos registros

El PGOU se conserva como un único instrumento, no se generan proyectos a partir
de los artículos o sectores incluidos en su normativa. El PDF es una rectificación
con publicación de la normativa, no un proyecto de obras nuevo de octubre de 2015.
La primera página distingue publicación del BOJA (19-10-2015), fecha del anuncio
(08-10-2015), aprobación de normativa a reserva de subsanación (13-02-2015) y toma
de conocimiento (19-03-2015). No se asigna una fecha genérica a estos actos.

El avance es un instrumento concreto de identificación y delimitación territorial,
aprobado con carácter de ordenanza municipal. Se incluye por su contenido de
planeamiento, a diferencia de las ordenanzas generales de procedimientos que lo
acompañan. La primera página del BOP distingue el acuerdo de aprobación definitiva
del Pleno (01-03-2018) y la publicación (23-03-2018). No es una concesión individual
de licencia ni acredita obras ejecutadas.

Estas fechas proceden de la lectura de los PDF capturados, no del inventario HTML.
El parser extrae exclusivamente el inventario: deja `fecha_publicacion`,
`fecha_acuerdo`, `fecha_aprob` y `fase` en null en lugar de fijar como constantes
fechas o estados de los documentos de esta comprobación. La presencia en el
inventario actual no demuestra vigencia jurídica ni incorpora automáticamente
modificaciones posteriores.

## Implementación y límites

Se filtran títulos de las dos familias comprobadas dentro de `.entry-content`;
no se extraen enlaces del menú, formularios, licitaciones ni noticias. Los enlaces
con el mismo título normalizado se agrupan en un instrumento con varios
`documentos`, evitando duplicados por punto final o URL repetida. Se conservan
URL de inventario, URL original, URL HTTPS, URL final y SHA-256 del PDF descargado.
Cada extracción descarga los documentos y exige respuesta correcta, cabecera PDF
y dominio oficial. Los identificadores derivan del título, no del orden de la lista.

La página fuente es una lista estática sin paginación. Si aparece paginación
WordPress en su contenido se detiene con error para revisar la navegación; no hay
un límite de páginas que recorte silenciosamente el inventario. También se falla
ante inventario vacío, estructura ausente o documento inválido. Las actualizaciones
refrescan el inventario completo y no usan un cursor incremental.

No hay geometrías verificadas, direcciones de obras ni coordenadas inventadas.
`publication_ready=false`. Licencias, programación y jitter permanecen desactivados.
El adaptador no pretende cubrir todo el planeamiento provincial ni todas las
obras municipales. Los títulos distintos se consideran instrumentos distintos;
no se intenta deducir relaciones entre revisiones con nombres diferentes.

## Validación reproducida y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_villanueva_de_cordoba -v
```

Tres tests correctos: filtrado y agrupación documental, errores ante estructura,
paginación o enlaces inválidos, carga por manifest y licencias deshabilitadas.
Se ejecutó `load_portal_adapter(load_manifest('villanueva-de-cordoba'))` con
`portal.config.capture_dir='evidence'`, seguido de
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **2 registros reales**.
La llamada usa también la anotación semántica del registro compartido de adaptadores;
las categorías quedan desconocidas, sin atribuirles una categoría por conjetura.

`evidence/validation.json` contiene recuento, URLs, fecha de extracción y límites.
`evidence/urbanismo.html`, `evidence/ordenanzas.html` y los PDF contienen las
capturas; `pgou.txt` y `avance.txt` son lecturas locales mediante `pdftotext` para
esta investigación. Las capturas y JSONL son evidencia local, no fuentes a incorporar
al repositorio. No se necesitan nuevas dependencias ni cambios compartidos.
