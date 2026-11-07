# Bermeo — INE 48017, Bizkaia

Verificación: 2026-11-07. Adaptador exclusivo para Bermeo. Fuente primaria:
[Plan orokorra, inventario municipal](https://www.bermeo.eus/1453.html), HTTP 200.

## Descubrimiento y cobertura

La portada municipal enlaza «Plan orokorra» a 1453.html. La página de transparencia
[Normativa urbanística](https://www.bermeo.eus/1287.html) enlaza en cambio a
`plan_orokorra.html#c3845`: en esta verificación devuelve contenido de portada,
no el inventario. El adaptador exige `#seccioncontenido` y los encabezados del
inventario; una portada con HTTP 200 no se admite como extracción válida.

Se extraen **8 instrumentos y 42 enlaces**, agrupando sus memorias, planos,
resúmenes, acuerdos y anuncios. No se generan proyectos por cada PDF:

| Identidad estable | Instrumento | Enlaces |
| --- | --- | ---: |
| casco-antiguo | Revisión del plan especial del casco antiguo, aprobación inicial | 20 |
| pgou | Plan general, sección «BEHIN BETIKOAK» | 5 |
| area-21-2-parcelas-6-9 | Plan especial parcelas 6 y 9, Matxitxako Bidea | 5 |
| area-6-1-2 | Plan especial del área 6.1.2 y aprobación definitiva | 2 |
| catalogo-pgou | Modificación del catálogo del HAPO | 1 |
| olalde | Plan de renovación del entorno de Olalde | 5 |
| area-21-2-parcelas-8-11 | Plan especial parcelas 8 y 11 del área 21.2 | 3 |
| subestacion | Plan especial para la transformación de la subestación | 1 |

El inventario es un listado HTML estático, sin paginación observada. Se procesa
todo el contenido central; un documento no clasificado o controles de paginación
provocan error, nunca corte silencioso. Las familias de documentos y los títulos
se validan contra la estructura revisada. Los enlaces nuevos de familias conocidas
se conservan; una nueva familia requiere ampliar el parser. Se exige la presencia
de los ocho instrumentos revisados para detectar pérdida de contenido.

Los cinco enlaces del PGOU incluyen los índices [Planoak](https://www.bermeo.eus/813.html)
y [Etendako guneak](https://www.bermeo.eus/1429.html). Se retienen como
`tipo: indice_documentos`; no se recorren sus documentos descendientes. Cobertura
parcial del inventario de documentos, no un archivo exhaustivo de planeamiento,
proyectos, obras ni instrumentos legalmente vigentes. El catálogo provincial
[Planeamiento urbanístico — Bermeo](https://www.opendatabizkaia.eus/es/dataset/planeamiento-urbanistico-bermeo)
ofrece otra fuente de datos orientativos/agregados; no se mezcla con estos expedientes.
No se extraen noticias, formularios, licitaciones ni licencias concedidas.

## Semántica y procedencia

Cada registro conserva título municipal, URL del inventario y todos sus enlaces
con etiqueta original y `source_url`. IDs por instrumento independientes del orden.
La familia 6.1.2 agrupa el resumen ejecutivo y `II-5559_eus.pdf`, aunque este último
está mal anidado en el HTML dentro del elemento de las parcelas 8 y 11. El anuncio
`II-1623_eus.pdf` pertenece a las parcelas 6 y 9, no al PGOU anterior en la lista.

Se capturaron y comprobaron cinco anuncios PDF oficiales servidos por el municipio:
`II-552_eus.pdf`, `II-1623_eus.pdf`, `II-5559_eus.pdf`, `II-3866_eus.pdf` y
`4-_iragarkia.pdf`. Por ejemplo, II-1623 es una aprobación inicial condicionada:
el encabezado general «BEHIN BETIKOAK» no permite atribuir aprobación definitiva
a todos los documentos que siguen. Solo se asigna fase desde etiquetas explícitas
del instrumento, o desde esa sección para el propio PGOU. Fase no equivale a obra
ejecutada, licencia concedida ni verificación independiente de vigencia jurídica.

El parser extrae únicamente las fechas explícitas de publicación BAO de las etiquetas:
2025-02-07 (casco antiguo) y 2022-03-21 (catálogo). No lee el contenido PDF para extraer
fechas; `fecha_acuerdo` y `fecha_aprob` permanecen nulas. La diferencia es material:
II-552 se publica el 07-02-2025 y relata acuerdo de 26-11-2024; II-5559 se publica el
14-11-2023 y relata acuerdo de 28-09-2023. Ninguna fecha se deduce del nombre del
archivo, fecha del calendario de la web o fecha de descarga. Otros instrumentos
pueden tener fechas en los PDF que esta cobertura no extrae.

## Geometría y límites

`geometry_status: unavailable`. Hay documentación gráfica y planos PDF, pero no
se ha verificado una geometría vectorial enlazable por identidad a cada instrumento.
No se convierten planos en geometría, no se asigna centroide municipal ni se inventan
coordenadas o CRS. `publication_ready: false`. No se ha verificado un registro de
licencias concedidas; ambos métodos de licencias escriben vacío y devuelven disabled.

## Verificación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_bermeo -v`: 6 pruebas, correctas.
- Ejecución real de `BermeoAyuntamientoAdapter(config={'evidence_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 8 registros.
- Pruebas sin red: agrupación, fechas, duplicados, documentos nuevos, paginación,
  fuentes desconocidas/externas, portada, fecha inválida, escritura segura y manifiesto.
- Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, captura
  `evidence/inventory-live.html`, páginas de descubrimiento y los cinco anuncios PDF.
  Los PDF restantes se conservan como enlaces; no se afirma haberlos descargado todos.

Actualización por instantánea completa. Los errores de descarga o parser dejan
intacto el JSONL anterior. Programación y licencias desactivadas;
`geocode.jitter_missing: false`. Sin cambios compartidos ni dependencias nuevas.
