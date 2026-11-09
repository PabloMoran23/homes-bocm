# Vélez-Rubio — INE 04099, Almería

Investigación y extracción en vivo: 9 de noviembre de 2026.

## Fuente oficial y descubrimiento

El sitio municipal https://www.velezrubio.es/ identifica el ayuntamiento mediante
CIF P-0409900-H y domicilio Plaza de la Encarnación, 1, Vélez Rubio (Almería).
El inventario utilizado es su [tablón de planeamiento](https://www.velezrubio.es/Servicios/cmsdipro/index.nsf/tablon_view_entidad_rol_categoria12.xsp?cat1=Territorio&cat2=Planeamiento+Urban%C3%ADstico&p=VelezR).
Se comprobaron también la página municipal de Urbanismo alojada en Diputación
(https://www.dipalme.org/Servicios/Organizacion/Organiza.nsf/tablon/DEC1C3705083388A41256BF800388F73),
que describe funciones, y el servicio de solicitud de licencia de obra menor
(documentId=0C51B3FBA6662BFBC1257DFC003F5CA6, p=SedeVelezR), que es un
trámite reutilizable y no evidencia de concesión. No se extraen como actuaciones.

La infraestructura Diputación/Domino sirve páginas de otros municipios incluso
bajo este dominio. El adapter exige p=VelezR y verifica la entidad de cada ficha,
no acepta como pertenencia municipal el dominio por sí solo.

## Inventario y unidad de extracción

El listado inicial presenta nueve categorías plegadas. El adapter obtiene una
sesión anónima y envía exclusivamente formularios de estado de vista XPages para
desplegarlas todas. En la consulta se observaron once fichas, sin paginador.
Las expansiones se comprueban hasta que no queda ninguna plegada. Si aparecen
paginadores, falta el contenedor o se atasca el despliegue, falla explícitamente;
no guarda una primera página como extracción completa. No hay corte silencioso:
el límite de seguridad también produce error.

Ocho fichas son instrumentos/proyectos reales. Se excluyen dos ordenanzas y la
adhesión al pacto de accesibilidad. Resultado previsto y verificado en la ejecución:
seis conjuntos documentales:

- Estudio de Detalle, finca registral 23.716, Av. Andalucía / Calle Sol / Calle Vaguada:
  ficha 94D0B9789D66CD89C1258DC40045C596; certificado de Pleno, memoria y planos.
- NNSS y modificación puntual del Plan Especial de Protección del Casco Histórico:
  ficha 634449F21E65C936C1258618002C0993; un único PDF publicado como paquete conjunto.
  No se separan artificialmente las normas y la modificación.
- Actuación extraordinaria en paraje Canete, polígono 39, parcelas 2, 3 y 50,
  Uniformes Gary’s: ficha 308CF5AB2958E99CC12589FA002FC6E8; proyecto y anuncio BOP.
- Ampliación porcina, polígono 30, parcelas 637, 646 y 1.028, María Martínez Cabrera:
  fichas 2434E0B0EEBE7D66C125894B0027ED13 y E4683D96B628584EC12589AA0027E2E0.
- Ampliación porcina, polígono 50, parcelas 174 y 180, Juan Pedro Fernández Molina:
  fichas 4ED9C108B9617ACBC125894B002771E9 y 2523C9C47E89D362C12589AA00271E3A.
- Ampliación porcina, polígono 51, parcela 12, Bernardo López Martínez:
  ficha E7B20306B7F92104C12589AA002677F1; proyecto y anuncio BOP.

Las dos parejas porcinas publicadas el 03/02/2023 y 09/05/2023 se agrupan mediante
polígono, conjunto completo de parcelas y promotor. La comprobación documental
corrobora las referencias 2022/409942/003-125/00001 y 2020/409942/003-011/00010,
respectivamente. No se agrupan sólo por categoría o parecido de título. Todas las
fichas, fechas, etiquetas de adjunto y enlaces distintos permanecen en
`publicaciones` y `documentos`; no se descartan las URL de copias repetidas.

## Semántica y límites

`fecha_publicacion` es la primera fecha de publicación de ficha observada en el
conjunto; cada publicación conserva la suya. No equivale a publicación en BOP,
aprobación ni concesión. Por ejemplo, el certificado del estudio indica acuerdo
del 26/02/2026 y firma del 11/03/2026; la ficha fue publicada el 24/03/2026.
El adapter no lee narrativas PDF, por lo que `fecha_acuerdo` y `fecha_aprob`
quedan nulas, incluso cuando el documento permite investigarlas manualmente.
Otro ejemplo: los BOP de las dos ampliaciones son del 23 y 27/02/2023, aunque
ambas fichas posteriores se publicaron en mayo. No se trasladan esas fechas al
campo de acuerdo. El anuncio de Bernardo contiene una fecha literal de acuerdo
31/03/2022 junto a antecedentes de 2023: no se corrige ni adivina el año.

Se descargaron muestras PDF válidas para los seis conjuntos y los anuncios de
las parejas agrupadas. El PDF de NNSS es escaneado y `pdftotext` no extrajo texto;
se conserva la identificación del paquete por la ficha oficial, sin afirmar
vigencia actual ni aprobación de todas sus piezas. La muestra de Canete sí
contiene la memoria del área logística y fabricación textil y de calzado, no un
mero anuncio de contratación. Las ampliaciones conservan sus proyectos técnicos
además de anuncios. No se tratan estos proyectos como licencias concedidas.

Cobertura parcial: inventario documental actualmente expuesto de planeamiento,
no registro histórico completo, ni censo de obras públicas ni licencias.
`update_proyectos` vuelve a obtener la instantánea completa; no usa un cursor
que pudiera perder fichas antiguas. Sin coordenadas o geometría verificadas,
`publication_ready=false`. Licencias, programación y jitter están desactivados.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_velez_rubio -v
```

Seis pruebas offline: procedencia, distinción de fechas, agrupación y aislamiento
por parcelas, exclusión de recursos ajenos, rechazo de otra entidad, paginación
sobrevenida y bloqueo ante expansión atascada. Los fixtures son sintéticos y no
se usan como registros de salida.

Extracción real mediante `VelezRubioAyuntamientoAdapter.backfill_proyectos`,
resolviendo antes el manifest con `load_manifest('velez-rubio')`. Seis registros,
ocho publicaciones y diecisiete enlaces documentales con procedencia.
Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas de cada respuesta de la extracción en
`evidence/live/`, inventarios de descubrimiento y fichas `detail-*.html`, muestras
`sample-*.pdf` y transcripciones `sample-*.txt`. El informe de validación registra
URL, limitaciones, instante UTC y hashes de las respuestas capturadas.
