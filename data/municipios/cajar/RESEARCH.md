# Cájar — Granada — INE 18036

Investigación y extracción en vivo: 9 de noviembre de 2026.

## Fuentes oficiales descubiertas

- Web municipal: https://cajar.es/ y https://cajar.es/urbanismo-y-deportes/.
  Las peticiones HTTPS verificadas con requests devolvieron 403. Las páginas
  indexadas de urbanismo describen competencias, no un registro de concesiones.
  No se convierten formularios, noticias genéricas ni licitaciones en proyectos.
- Portal oficial accesible sin identificación:
  https://cajar.sedelectronica.es/transparency.
  El apartado 7, urbanismo/obras/medio ambiente, anuncia nueve documentos:
  https://cajar.sedelectronica.es/transparency/a9821f4a-dcc3-4195-81e1-28ccbb3f8d28/.
  Las carpetas 7.1 planeamiento, 7.2 planes medioambientales, 7.3 normativa
  urbanística y 7.5 indicadores muestran cero documentos. La carpeta 7.6 contiene
  dos documentos de información pública ambiental, fuera del alcance seleccionado.
- Inventario extraído, 7.4 OBRAS PÚBLICAS E INFRAESTRUCTURAS:
  https://cajar.sedelectronica.es/transparency/99df580b-c3d4-4a61-a5ba-c89c626ea539/.
  Una carpeta, EXPROPIACION FORZOSA AVDA. DE HUÉTOR, siete documentos:
  https://cajar.sedelectronica.es/transparency/daeb6707-9c68-4492-98c7-9560f2f1c768/.
- Proyecto técnico municipal:
  https://cajar.sedelectronica.es/preview-document/30c18b1d-daa1-4a00-9b2a-a8b14cd655bc.
  Se verificó el visor y se descargó su PDF de 14.459.668 bytes, firma `%PDF-`.
  El texto local confirma 216 páginas y capítulos de objeto de las obras,
  emplazamiento Avenida Huétor Vega, acerado, saneamiento, abastecimiento,
  electricidad, alumbrado y telecomunicaciones. No es una mera convocatoria.

## Unidad y semántica

Resultado real: **un proyecto**, PROYECTO ACERADO AVDA. HUETOR VEGA. Conserva
siete documentos con título y URL permanente de visor: proyecto, certificado de
acuerdo de pleno, informe jurídico, informe técnico-urbanístico-legal, memoria
justificativa, anuncio de información pública y BOP Nº 156 de 14-08-26. No se
multiplica la actuación por el número de archivos. El ID deriva de la carpeta,
no del token temporal de la sesión ni del título del archivo.

La fecha de creación del proyecto en el visor es 12-ago-2026; el PDF muestra
firmas técnicas de agosto. Ninguna se trata como fecha de aprobación. El nombre
del BOP conserva su fecha como metadato del documento, sin atribuirla al acuerdo.
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` permanecen nulas; no se ha
interpretado el certificado de pleno para extraer una fecha. Tampoco se afirma
que la obra esté adjudicada, ejecutada o terminada. No hay geometría verificada,
coordenadas ni fase inferidas; `publication_ready=false`.

## Recorrido y límites

El adaptador consulta en vivo el inventario de obras y recorre todas sus
subcarpetas no vacías mediante las acciones públicas Wicket y la cabecera
`Ajax-Location`. No ejecuta JavaScript externo. Conserva los enlaces permanentes
`preview-document`, sin fijar las URLs temporales de descarga. Comprueba el
recuento anunciado de cada carpeta contra los documentos encontrados
recursivamente. No se observó paginación en las páginas verificadas; un control
activo de paginación, un recuento discordante, un ciclo o una estructura
inesperada provocan error explícito antes de escribir el resultado. No hay un
límite de registros que recorte silenciosamente el inventario.

Cobertura parcial y explícita: sólo el inventario público de obras 7.4. No es
un histórico completo municipal, ni un inventario exhaustivo de planeamiento,
ni un registro de licencias concedidas. Los contadores cero del portal no
prueban inexistencia de instrumentos fuera de esa fuente. No se amplió a
anuncios históricos del BOJA ni a noticias de cortes de tráfico. Un documento
sin un proyecto técnico identificado en su carpeta no genera por sí solo una
actuación; varios proyectos técnicos en una carpeta requieren revisar la
agrupación y provocan error. Los cambios incrementales refrescan la instantánea
completa sin inventar una cronología. Licencias, programación y jitter de
geocodificación desactivados en el manifest.

## Validación reproducible y evidencia local

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_cajar -v`: once pruebas correctas.
Cubren agrupación y procedencia, fechas y geometría ausentes, exclusión de
formularios/anuncios, cambios de HTML, ambigüedad, enlaces ajenos, paginación,
contadores, manifest y recorrido completo con sesión simulada.

Extracción directa real (sin base de datos ni publicación):

```python
from pathlib import Path
from municipio.adapters.cajar import CajarAyuntamientoAdapter
adapter = CajarAyuntamientoAdapter(config={'evidence_dir': 'evidence/captures'})
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

`evidence/validation.json` contiene `live_records=1`, siete documentos,
`source_urls` y limitaciones. Se conservan las páginas oficiales bajo
`evidence/`, las capturas de la ejecución bajo `evidence/captures/`, y el PDF
`evidence/proyecto-acerado.pdf` con su texto extraído. La evidencia es local y
no forma parte de los cuatro archivos fuente entregados.
