# Santa María de Cayón — Cantabria — INE 39074

Verificación y extracción real: 2026-11-07. Cobertura parcial de planeamiento,
no de licencias concedidas ni de todas las obras del municipio.

## Descubrimiento y fuentes oficiales

La sección municipal [Urbanismo y Obras](https://www.santamariadecayon.es/index.php/173-obras-urbanismo)
enlaza desde su navegación el [inventario Plan General de Ordenación Urbana](https://www.santamariadecayon.es/index.php/servicios-municipales/sm-urbanismo-obras/sm-urbanismo-pgou).
Esta última página, HTTP 200, es el punto de entrada del adaptador; los enlaces
se descubren en el cuerpo del artículo, excluyendo menús y noticias laterales.
No se fija una noticia individual como origen ni una lista prefijada de expedientes.

El inventario declara el PGOU en elaboración. Esa declaración genérica no genera
un registro adicional: no proporciona allí un documento del nuevo PGOU.
Se extraen los tres instrumentos documentados:

- **Normas Subsidiarias de 1987**: [texto municipal](https://www.santamariadecayon.es/images/stories/cayon/pdf/ObrasUrbanismo/PGOU/NORMAS_SUBSIDIARIAS_1987.pdf).
  La fecha 23/01/1987 de la portada corresponde a la remisión firmada por el alcalde;
  no se transforma en fecha de aprobación o publicación. Sin fechas exactas extraídas.
- **Modificación del régimen de suelo rústico, expediente 2013/16**:
  [anuncio original CVE-2014-16927](https://www.santamariadecayon.es/images/stories/cayon/pdf/ObrasUrbanismo/PGOU/MofificacionPuntualNormasSubsidarias.pdf),
  publicado 02/12/2014, acuerdo plenario 30/10/2014;
  [corrección CVE-2014-17830](https://www.santamariadecayon.es/images/stories/cayon/pdf/ObrasUrbanismo/PGOU/BOC2014-17830_CORRECTO.pdf),
  publicada 17/12/2014, con el anexo normativo. Ambos PDF pertenecen al mismo
  instrumento. Se conserva además la referencia municipal al
  [boletín completo](https://boc.cantabria.es/boces/verBoletin.do?idBolOrd=14573),
  sin atribuir todos sus anuncios al municipio ni usarlo para inferir fechas.
- **Modificación en suelo productivo municipal, expediente 2021/746**:
  [BOC CVE-2025-2178](https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=417482),
  publicado 14/04/2025, acuerdo plenario 31/01/2025; documento de 133 páginas.
  La firma de 13/03/2025 y la fecha de redacción de octubre de 2024 no son
  fechas de aprobación. Un registro para todo el PDF, incluidos sus anexos.

Los cuatro PDF se descargan y se comprueban como PDF durante cada extracción;
se conserva su SHA256. Las fechas salen del texto de la primera página mediante
`pdftotext -layout`, ejecutable ya instalado, sin añadir paquetes. Los campos
`fecha_publicacion` y `fecha_acuerdo` conservan su significado explícito y la URL
que los acredita; no se rellena una `fecha` genérica ni `fecha_aprob` inferida.
La corrección tiene fecha propia en `documentos`, sin sustituir la publicación original.

## Otras fuentes revisadas y límites

[Documentación urbanística](https://www.santamariadecayon.es/index.php/servicios-municipales/sm-urbanismo-obras/sm-documentacion)
solo ofrece un enlace regional al Plan Especial del Territorio Pasiego; no se ha
acreditado aquí su inventario documental y no se incorpora como otro proyecto local.
[Trámites / documentos](https://www.santamariadecayon.es/index.php/tramites-online/to-documentos)
publica modelos de solicitud y declaraciones responsables, no concesiones verificadas.
La categoría de noticias contiene obras junto a avisos, meteorología y otras noticias;
no se trata como inventario de expedientes. No se extraen anuncios de contratación.

El alcance es **todo el inventario documental del artículo municipal PGOU**,
no todo el planeamiento regional ni todos los expedientes históricos. Actualmente
no presenta paginación. Si aparece paginación o desaparece el cuerpo/documentación,
el adaptador falla explícitamente; no acepta una primera página truncada.
Una nueva descarga completa reemplaza atómicamente la instantánea, sin marcas de
fecha que puedan omitir documentos antiguos recién enlazados. No mantiene un archivo
histórico de enlaces retirados ni usa `state_path` como cursor incremental.

## Geometría y validación

geometry_status: unavailable

No hay geometría vectorial ni coordenadas verificadas asociadas a estos registros.
Los planos incluidos en documentos no se convierten en puntos inventados.
`schedule.enabled=false`, `licencias.enabled=false`, `geocode.jitter_missing=false`.

Pruebas con el runtime preinstalado:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_santa_maria_de_cayon -v
```

Cinco pruebas cubren agrupación, referencias y duplicados, fechas explícitas frente
a firmas, ausencia de coordenadas, rechazo de cambios de inventario/paginación y
carga mediante el registro común con licencias vacías sin tráfico de red.
Extracción real mediante `load_manifest` y `load_portal_adapter`: **3 registros**,
**4 PDF**, más referencia al boletín de 2013/16. Evidencia local no destinada a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML/PDF y textos
PDF de investigación. No se han ejecutado publicación, sincronización ni despliegues.
