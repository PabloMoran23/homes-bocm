# Yuncos (INE 45205), Toledo

Verificación en vivo: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron `municipio/adapters/portal.py`, el cargador del manifiesto, el registro
de adaptadores y los ejemplos Manlleu y Chipiona antes de implementar.

## Fuentes oficiales descubiertas

- [Web del Ayuntamiento](https://yuncos.es/): enlaza Urbanismo, Normativa Urbanística y la sede municipal.
- [Urbanismo](https://yuncos.es/urbanismo/): solicitudes de obra menor, obra mayor y consulta de expedientes. Son formularios, no concesiones; no se extraen licencias.
- [Normativa Urbanística](https://yuncos.es/normativa-urbanistica/): el botón «VER DOCUMENTOS» conduce a [7. Urbanismo, Obras Públicas y Medio Ambiente](https://yuncos.sedelectronica.es/transparency/ad2293ec-1d42-4392-b374-807bf8a2cfa9/).
- [7.1. Planeamiento Urbanístico](https://yuncos.sedelectronica.es/transparency/88406f55-4cff-40e9-b00f-eb5d4101f315/): fuente de este adaptador. Anuncia 52 documentos recursivos: [Normas Urbanísticas](https://yuncos.sedelectronica.es/transparency/bb5bb761-96c9-4d16-ac9d-94a38b5015a6/) (11) y [Planos de Ordenación](https://yuncos.sedelectronica.es/transparency/2491efcd-46b6-4438-88a6-08eb68b7f00c/) (41).

El índice superior también anuncia planes y programas medioambientales (68),
normativa urbanística (4), obras públicas e infraestructuras (0), indicadores (0)
y documentos en información pública (11). Estas secciones no forman parte de la
cobertura implementada. Tampoco se extraen noticias, actas ni contratación: un
anuncio de licitación no constituye por sí mismo un proyecto verificado.

## Extracción y agrupación

La sede sirve HTML y componentes XML Wicket. El adaptador solicita exclusivamente
las acciones públicas de carpetas y «Mostrar más», sin ejecutar JavaScript.
Resuelve las redirecciones a carpetas canónicas dentro del mismo dominio HTTPS.
Recorre todas las páginas y subcarpetas y compara sus documentos únicos con el
recuento recursivo anunciado. Un ciclo, recuento incompleto o respuesta inesperada
produce un error antes de sustituir el archivo de salida; no se publica una muestra
truncada. No se necesita identificación ni acceso a expedientes privados.

La extracción en vivo recorrió los **52 documentos**. Se generan **4 instrumentos**
con **28 documentos** asociados:

| Instrumento | Documentos asociados |
| --- | ---: |
| NNSS de Yuncos, texto refundido y anexos identificados como NNSS | 5 |
| PERI de la Unidad de Actuación Plaza Casa-Palacio | 1 |
| Plan Parcial de Ordenación Sector 18, memoria y planos | 2 |
| Plan Parcial de Ordenación Sector 26, memoria y subcarpeta de planos | 20 |

Los 24 documentos restantes quedan enumerados en `excluded_documents` del informe
local: cartografía general, normativa S-5, edificios inventariados y vías pecuarias.
Se recorren, pero no se convierten en proyectos ni se atribuyen a un instrumento
sin una identificación explícita. Las láminas de la carpeta del Sector 26 se
vinculan a ese plan por su carpeta, aunque su título individual no cite el sector.
Los identificadores de los cuatro instrumentos son estables e independientes de
los enlaces de sesión Wicket. Cada documento conserva título, URL pública de
previsualización, carpeta y URL de inventario canónico. Los enlaces de documento
son páginas de procedencia, no se presentan como descargas PDF directas.

## Fechas, estado y alcance

«Mayo 2012» se conserva en los títulos originales de documentos NNSS; no se
transforma en una fecha de aprobación o publicación. La previsualización oficial
del texto refundido muestra «Fecha de creación 23-oct-2019 10:44:39»: es metadato
del archivo y tampoco se utiliza como fecha del instrumento. El contenido de los
PDF no se analiza. No se acredita vigencia, aprobación definitiva ni ejecución
por el hecho de figurar en el inventario.

`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` son nulos.
No hay coordenadas o geometrías verificadas: `lat`, `lon` y `geometry` son nulos,
`publication_ready=false` y `geocode.jitter_missing=false`. No se usa el centroide
municipal. `schedule.enabled=false` y `licencias.enabled=false`.

La actualización vuelve a leer la instantánea completa del inventario; no simula
incrementalidad ni utiliza el estado para omitir carpetas. Cobertura parcial del
municipio, completa para el recorrido del inventario 7.1 verificado.

## Validación reproducible

Pruebas sin red:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_yuncos -v
```

Nueve pruebas comprueban XML y paginación, subcarpetas, agrupación y ausencia de
fechas inferidas, exclusión de formularios, destinos externos, ciclos, recuentos
incompletos, fallo sin instrumentos y configuración del manifiesto/licencias.
La extracción real se ejecutó mediante `load_manifest('yuncos')` y
`load_portal_adapter(...)`, con `capture_dir='evidence/live'`, escribiendo
`evidence/proyectos.jsonl` y `evidence/validation.json`. Las capturas iniciales y
las respuestas del recorrido están bajo `evidence/`, exclusivamente locales.
El informe incluye la clasificación derivada del registro compartido; estos
instrumentos documentales sin expediente acreditado no se anuncian como actividad
aprobada o publicable.
