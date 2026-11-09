# Cedillo del Condado — Toledo — INE 45047

Investigación y ejecución en vivo: 9 de noviembre de 2026.

## Fuentes oficiales e inventarios descubiertos

La web del [Ayuntamiento](https://www.cedillodelcondado.es/) enlaza la sede
`cedillodelcondado.sedelectronica.es`; no se debe confundir con la sede de Cedillo
(Cáceres). El [portal de transparencia](https://cedillodelcondado.sedelectronica.es/transparency)
expone carpetas mediante navegación anónima Wicket. Las llamadas de carpeta
responden con `Ajax-Location`, que permite obtener URLs estables sin guardar tokens
transitorios como identidad del instrumento.

El [apartado 7](https://cedillodelcondado.sedelectronica.es/transparency/49315160-24c0-4782-a8dc-f3dd69121fa9/)
indica 144 documentos: 7.1 Planeamiento Urbanístico (98), 7.3 Normativa Urbanística
(45), y una publicación sobre la planta fotovoltaica La Vaguada en la raíz. Las
carpetas 7.2, 7.4 y 7.5 indican cero documentos. El apartado de normativa tiene
«Mostrar más»; no se ha tomado su primera página como inventario completo.

La fuente seleccionada es [7.1 Planeamiento Urbanístico](https://cedillodelcondado.sedelectronica.es/transparency/f738017d-4b56-41c3-8b4a-02d0964b7a2f/).
Contiene siete enlaces sobre modificaciones NNSS/anuncios y una carpeta
[PLAN DE ORDENACION MUNICIPAL](https://cedillodelcondado.sedelectronica.es/transparency/cb778d70-cfd4-4434-ad3e-eae2af1a22e1/)
con **91 documentos**. Solo esta carpeta constituye la cobertura del adaptador.
Las modificaciones NNSS se dejan fuera: sus títulos repetidos no permiten
establecer inequívocamente su agrupación por instrumento sin investigación
adicional de sus contenidos. No se convierten anuncios genéricos en proyectos.

## Cobertura y agrupación

Se produce **un registro real**, el POM, con 91 objetos `documentos` que conservan
título, URL estable de vista documental, URL del inventario y ruta de carpeta.
El identificador depende del UUID de la carpeta, no del orden, título de un PDF
o token de sesión. Los planos y memorias son partes del instrumento, no 91
proyectos separados.

Desglose comprobado en vivo:

- Raíz del POM: 31 documentos.
- [0.1 Memorias](https://cedillodelcondado.sedelectronica.es/transparency/662179b7-31b8-48a6-827a-8dd550b95ef6/): cuatro documentos (normas, fichas de gestión y memorias informativa y justificativa).
- [0.2 Planos](https://cedillodelcondado.sedelectronica.es/transparency/14901e0d-6f89-42d3-aa02-edf4b28ba386/): 56 documentos.

El scraper recorre todas las páginas «Mostrar más» y subcarpetas de este ámbito,
interpreta únicamente los fragmentos HTML de `component` de las respuestas XML y
no ejecuta JavaScript de las fuentes. Cada carpeta debe alcanzar el contador
anunciado por su padre. Paginación sin progreso, ciclos, límites de recorrido,
conteos incompletos, falta de carpeta o ausencia de documentos provocan error
antes de escribir la salida. No hay truncamiento silencioso ni fallback sintético.
Las actualizaciones vuelven a obtener una instantánea completa.

## Procedencia y semántica

La [vista de MEMORIA INFORMATIVA](https://cedillodelcondado.sedelectronica.es/preview-document/94062187-c791-4614-84f0-201b77928d64)
permite descargar un PDF real: HTTP 200, `application/pdf`, firma `%PDF-`,
10.176.797 bytes. La primera página identifica el Plan de Ordenación Municipal
de Cedillo del Condado, Ayuntamiento de Cedillo del Condado (Toledo), «Documento
para Aprobación Inicial», julio de 2020. Es la fecha y descripción de una versión
documental; no acredita un acuerdo de aprobación inicial ni definitiva, y no
se asigna a `fecha_aprob`, `fecha_acuerdo` o `fecha_publicacion`.

Las vistas de documentos muestran fechas de creación del sistema (por ejemplo,
una ficha de catálogo tiene 30-jul-2021). No se convierten en fechas de publicación
oficial ni de acuerdo. Todos los campos de fechas explícitas permanecen nulos;
no se infiere fase vigente, geometría, dirección ni coordenadas. Se declara
`publication_ready: false`. Licencias, programación y jitter están desactivados.

Cobertura parcial explícita: no se extraen el resto de 7.1, 7.3, tablón, contratación,
actas ni una historia completa de proyectos u obras. Tampoco se ha verificado un
registro de licencias concedidas. Los formularios de solicitud no son concesiones.
Los enlaces retenidos son vistas estables de documentos; los enlaces internos de
PDF pueden ser temporales y no se utilizan como claves.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Sin instalaciones, cambios compartidos, bases de datos, publicación ni despliegue.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_cedillo_del_condado -v
```

Ocho tests offline: agrupación, semántica sin fechas inventadas, enlaces documentales
reales y deduplicados, contadores obligatorios, XML Wicket sin ejecutar scripts,
paginación con subcarpetas, inventario incompleto, falta de progreso y ciclos.

La extracción real se ejecutó directamente con el adaptador:

```python
from pathlib import Path
from municipio.adapters.cedillo_del_condado import CedilloDelCondadoAyuntamientoAdapter
adapter = CedilloDelCondadoAyuntamientoAdapter(config={'capture_dir': 'evidence/live'})
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Resultado: un instrumento, 91 documentos, cuatro URLs de inventario, 17 capturas
de las peticiones del recorrido. Evidencia local no destinada a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/live/`, capturas
del descubrimiento, vista documental y `evidence/memoria-informativa.pdf`.
