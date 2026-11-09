# Zas — INE 15093, A Coruña (Galicia)

Revisión y extracción en vivo: 2026-11-09. Adaptador único:
`municipio.adapters.zas:ZasAyuntamientoAdapter`.

## Fuentes descubiertas y selección

- Web oficial municipal: https://concellodezas.gal/.
- Departamento municipal de urbanismo:
  https://concellodezas.gal/es/departamento/urbanismo/.
  La página indexada enlaza «Plan parcial Os Muiños», «Planeamento histórico»,
  «PGOM del Ayuntamiento de Zas» y modelos de solicitudes. La petición directa
  desde el runtime devuelve HTTP 403: no se extraen esos instrumentos ni se
  consideran los formularios licencias concedidas.
- Sede oficial: https://sede.concellodezas.gal/. No se ha verificado aquí un
  inventario extraíble de licencias concedidas; queda fuera de cobertura.
- Inventario oficial provincial seleccionado:
  https://plan-unico.dacoruna.gal/zas/ (HTTP 200 en requests, sin sesión).
  Publicador: **Deputación da Coruña**. Encabezado «PLAN ÚNICO Zas»; el payload
  público de la página también identifica `nombreOficial=Zas` y
  `dir3=L01150933`. No se trata de un portal de contratación ni de noticias.

El campo `proyectos.source: ayuntamiento` selecciona el adaptador de portal del
contrato existente; los registros identifican expresamente `source: diputacion`
y el organismo provincial. No atribuyen la publicación al Concello.

## Cobertura real y semántica

Se leen las **47 filas** de «Lista de obras e investimentos», comprobadas contra
el total oficial «Obras aprobadas». Se excluye el suministro de una miniexcavadora
de 2025: quedan **46 obras físicas de los ejercicios 2017–2025**. Ejemplos reales:
«Mellora capa rodaxe de Sobreira-O Sisto», «Rehabilitación enerxética da Escola
Infantil de Zas» y «Rede de saneamento de Rial de Abaixo». Se conservan el objeto
literal, ejercicio, presupuesto y aportación provincial en euros.

El selector ofrece también 2026, pero la tabla actual no contiene obras de ese
ejercicio. No se inventan actuaciones para completar un año. La cobertura es la
instantánea actual del POS+, no todas las obras, planeamiento o licencias de Zas.
«Obras aprobadas» es la clasificación del inventario de financiación: no acredita
finalización, adjudicación, comienzo de obra ni una licencia concedida.

El ejercicio presupuestario se guarda como `ejercicio`, nunca como una fecha.
`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son null: la fuente
no expone esos días. No se deducen del año ni de la fecha de consulta.

Cada fila tiene una identidad técnica hash de ejercicio y título normalizado;
no es un número de expediente administrativo ni un ID oficial. Los importes y
el orden no participan en el ID. Si aparece la misma identidad dos veces se
falla por ambigüedad. Filas de financiación con objetos parecidos no se fusionan
sin un identificador oficial que demuestre que son la misma actuación.

La vista móvil repite las obras: se procesa exclusivamente la tabla para evitar
duplicados. Se conserva el enlace al inventario en cada registro. Actualmente
las filas no enlazan expedientes o PDFs individuales, por lo que `documentos`
está vacío; cualquier enlace en la celda del objeto se retiene agrupado en esa
obra, sin convertirlo en otro proyecto. Las fotografías generales no se atribuyen
a obras individuales. No se ha descargado ni interpretado documentación ausente.

## Paginación, actualización y controles

La respuesta HTML completa contiene las 47 filas de todos los ejercicios;
no existe paginación activa. El selector de ejercicios es un filtro de esa
instantánea. No hay límite de filas ni corte por año en el extractor.
Se rechazan enlaces de página siguiente/cargas adicionales, un total distinto
del número de filas, esquema cambiado, municipio distinto, importes inválidos,
identidades ambiguas y categorías nuevas no revisadas. Un error no reemplaza
la salida anterior. `update_proyectos` vuelve a leer la instantánea completa y
no usa el ejercicio como marca temporal incremental.

No hay geometría enlazada a las filas: `geometry_status: unavailable`,
`geometry`, `lat` y `lon` null, `publication_ready: false`. No se ha verificado
una capa GIS que identifique estas obras ni se han geocodificado topónimos.
Sin expediente oficial, la política compartida de entidades puede requerir
revisión de identidad; este adaptador no inventa referencias para superarla.

## Validación reproducible y evidencias locales

Runtime empleado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_zas -v`: **7 pruebas pasan**. Comprueban
semántica y fechas ausentes, identidad estable ante reordenación, exclusión de
suministros, agrupación de enlaces, integridad/paginación, rechazo de formularios
y anuncios, conservación de salida tras error, actualización y manifest.

Extracción real mediante `ZasAyuntamientoAdapter.backfill_proyectos`, con el
manifest cargado y `capture_dir=evidence`: **46 registros**. Evidencias:

- `evidence/proyectos.jsonl`: registros reales extraídos.
- `evidence/pos-zas.html`: respuesta completa de la extracción en vivo.
- `evidence/validation.json`: recuentos, URL fuente, exclusión, años, limitaciones,
  fecha de consulta y SHA-256 de la captura.

Las evidencias son locales y no deben incluirse en un commit.
`schedule.enabled=false`, `licencias.enabled=false` y
`geocode.jitter_missing=false`. No se han usado bases de datos ni publicación.
