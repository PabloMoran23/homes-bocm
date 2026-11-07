# Sada — INE 15075, A Coruña, Galicia

Investigación y ejecución: 7 de noviembre de 2026. Adaptador único:
`municipio.adapters.sada:SadaAyuntamientoAdapter`.

## Fuentes oficiales y descubrimiento

El [área municipal de Alcaldía y Urbanismo](https://www.sada.gal/alcaldia)
enlaza los cuatro inventarios documentales utilizados. Se vuelve a consultar en
cada ejecución; no se generan registros a partir de una lista de títulos prefijada.
Los títulos y enlaces de documentos se extraen del HTML actual de cada ficha.

| Instrumento / ficha municipal | Documentos únicos extraídos |
| --- | ---: |
| [PXOM](https://www.sada.gal/plan-xeral-de-ordenacion-municipal) | 72 |
| [Plan Especial de Veigue](https://www.sada.gal/plan-especial-de-veigue) | 73 |
| [PERI A Lagoa](https://www.sada.gal/peri-a-lagoa) | 40 |
| [PERI A Cañota](https://www.sada.gal/peri-a-canota) | 52 |

Son **4 instrumentos reales y 237 enlaces documentales únicos**, no 237 proyectos.
Cada instrumento conserva `documentos` con título, URL y `source_urls` de las páginas
que enlazan cada documento. Planos, memorias, normas, índices, órdenes y separatas
se agrupan; no se convierten individualmente en actuaciones físicas ni licencias.
Los títulos abreviados PERI son los publicados en h1; el contenido describe el
ámbito APR-PERI-D3.6 de la rúa da Lagoa y el núcleo rural de A Cañota.

La página de A Lagoa contiene un enlace a una memoria con ruta `peri_canota` y
código `2022_U035_000006_15075_PERI_202408_AD`. Se asigna a Cañota y se mantiene
A Lagoa como procedencia. El agrupador resuelve esto por la ruta documental,
no por la página que contiene el enlace. Cañota repite algún enlace; se deduplica
por URL dentro de su instrumento. URLs diferentes se conservan incluso si el
título se parece; no se ha comparado el contenido binario de los 237 documentos.

También se localizaron las versiones
[noticia de Veigue](https://www.sada.gal/plan-especial-veigue-sada) y
[versión alternativa](https://www.sada.gal/plan-especial-de-veigue-es), con el mismo
paquete de documentos. Se usa la ficha enlazada desde el área para evitar duplicar
el instrumento y confundir el 15/03/2024 de la noticia con una aprobación.
El área enlaza además un historial del PXOM e impresos de urbanismo: quedan
fuera del alcance de estos cuatro paquetes actuales. Formularios de licencia,
anuncios de contratación y noticias laterales no se extraen como proyectos.

## Semántica y límites

La ficha PXOM explicita `PXOM Aprobación definitiva (11/10/2017)` y la publicación
en DOG de la orden el **29/11/2017**. Se guardan respectivamente `fecha_aprob` y
`fecha_publicacion`, con sus fuentes y alcance. El carácter **parcial** y las
condiciones constan en la ficha y se indican en `alcance_aprobacion`. La primera
fecha corresponde a la orden, la segunda a su publicación oficial; ninguna
representa una fecha de actualización de la web. No se atribuyen fechas de
aprobación a Veigue, A Lagoa o A Cañota a partir de los códigos AI/AD ni de
los meses incorporados al nombre del archivo. No se infieren fases ni vigencia
jurídica actual de esos códigos.

Cobertura **parcial**: cuatro paquetes documentales publicados y accesibles desde
el área, sin garantía de exhaustividad de todos los planes, modificaciones u
obras municipales. No se extraen concesiones de licencias. La
[tabla oficial SIOTUGA](https://siotuga.xunta.gal/siotuga/urb) también identifica
Sada como INE 15075 y muestra el PXOM de 2017-10-11; no se integra su inventario
ni las evaluaciones ambientales de otras modificaciones en esta implementación.

Los cuatro paquetes observados tienen sus listados en una sola página, incluidos
los acordeones del HTML, sin paginación observada. No hay límites de documentos
ni de filas. Si aparece un control de paginación reconocido, falta una ficha
esperada, desaparece el contenido o aparece un PDF que no se puede clasificar,
la extracción falla antes de escribir un resultado incompleto. Las noticias
laterales están fuera de `div.pagina`. Cambios futuros del inventario necesitan
revisión: el alcance explícito es el conjunto de estas cuatro fichas.

Sin coordenadas ni geometrías inventadas, `geometry_status: unavailable` y
`publication_ready: false`. `schedule.enabled`, `geocode.jitter_missing` y
`licencias.enabled` son `false`. La política compartida de entidades anota las
cuatro filas como `unknown`; no las fuerza a otra clase. No se han alterado
fuentes compartidas, dependencias, base de datos ni procesos de publicación.

## Verificación reproducible y evidencias locales

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sada -v
```

Cinco pruebas correctas: descubrimiento, fechas distintas y aprobación parcial,
agrupación de documentos cruzados, conservación de más de 100 enlaces, rechazo
de contenido ausente/paginación/URLs ajenas y ejecución del adaptador con el
manifest. Las fixtures son sintéticas y están en el test; no dependen de la red
ni de las evidencias locales.

Extracción real ejecutada con `load_manifest('sada')`,
`manifest.portal.config['capture_dir'] = 'evidence'`,
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Resultado: **4 filas**, política compartida `status: ok`. Evidencias locales:

- `evidence/proyectos.jsonl`: registros reales completos con los documentos.
- `evidence/validation.json`: `live_records: 4`, URLs consultadas, límites,
  recuentos por instrumento, pruebas y verificaciones documentales.
- `evidence/alcaldia.html` y HTML de las cuatro fichas: capturas completas de la
  extracción; otras capturas de investigación se conservan también localmente.
- `evidence/document-1.prefix.bin` a `document-4.prefix.bin`: primeros 1024 bytes
  de un PDF por instrumento. Los cuatro respondieron HTTP 200,
  `application/pdf` y firma `%PDF-`. Son muestras parciales, no documentos
  completos ni una validación de todos los enlaces o de su contenido jurídico.

La evidencia queda local y no forma parte de los cuatro archivos fuente.
