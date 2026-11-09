# Beas (Huelva), INE 21011

Investigación y extracción live: 9 de noviembre de 2026. Se revisaron el contrato
`municipio/adapters/portal.py`, el cargador/esquema `municipio/manifest.py`, el
registro de adaptadores y los ejemplos de Chipiona y Hernani antes de implementar.

## Fuentes oficiales y alcance

Fuente implementada: [Planeamiento Urbanístico del Ayuntamiento de Beas](https://www.aytobeas.es/es/ayuntamiento/publicaciones-oficiales/Planeamiento-Urbanistico/).
Es un inventario documental vigente en la web, con ocho galerías de instrumentos,
no ocho obras nuevas ni ocho licencias concedidas. Cada galería `.sg-download-gallery`
contiene un encabezado `h4` y una tabla de documentos municipales PDF. Se recorren
todas las galerías y todos los enlaces de sus tablas, sin límite de registros.
No se observaron controles de paginación ni enlaces siguiente; el parser aborta
si detecta paginación, para exigir revisión en vez de devolver una cobertura
silenciosamente incompleta.

Inventario observado y extraído:

| Título literal municipal | Documentos |
| --- | ---: |
| 00 NNSS 1987 | 18 |
| 01 MODIFICACION 01 1993 | 15 |
| 02 MODIFICACION 02 1995 | 11 |
| 03 MODIFICACION 03 1997 | 5 |
| 04 MODIFICACION 04 2004 | 9 |
| 05 MODIFICACION 05 2015 | 13 |
| 06 MODIFICACION 06 2021 | 5 |
| 07 ADP LOUA 2012 | 21 |

Resultado live: **8 registros y 97 enlaces documentales**. NNSS, modificaciones y
adaptación LOUA son instrumentos de planeamiento reales. Se conserva el título
literal, la carpeta identificadora, la URL del inventario y cada documento con su
etiqueta y procedencia. El identificador deriva de la carpeta, no del orden de los
PDF ni de una fecha supuesta. El enlace principal lleva al primer documento de la
galería; `inventory_url` identifica el catálogo y `documentos` retiene el conjunto.
No se confunden los planos, certificados y publicaciones de un mismo instrumento
con proyectos separados. Los avisos y noticias de la barra lateral se excluyen,
incluido el anuncio de contratación de la redacción de la piscina.

Otras fuentes oficiales descubiertas:

- [Área municipal de Urbanismo](https://www.aytobeas.es/es/areas-tematicas/urbanismo/): contexto municipal, no se convierte en un proyecto genérico.
- [Sede electrónica de Beas](https://beas.sedelectronica.es/): no se ha verificado un registro abierto de licencias concedidas; no se extraen formularios ni anuncios como concesiones.
- [SITUA y visor de la Junta de Andalucía](https://www.juntadeandalucia.es/organismos/viviendajuventudyordenaciondelterritorio/areas/urbanismo/situa.html): inventario autonómico complementario, fuera del alcance de este adaptador municipal.
- [Evaluación ambiental autonómica, expediente 52441](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/52441): el descubrimiento web muestra la modificación puntual nº 7 del PGOU de Beas (DAE/HU/001/26). No aparece entre las ocho galerías municipales observadas y no se incorpora sin implementar esa fuente. Confirma que el inventario municipal no representa todo el planeamiento en tramitación.

## Semántica y limitaciones

Los años del título no se interpretan como fechas de acuerdo. No se extraen
`fecha_publicacion`, `fecha_acuerdo` ni `fecha_aprob`: los nombres «PUBLICACION AD»
y «CERTIFICADO APROBACION AI» solo se conservan como títulos documentales. No se
infiere aprobación definitiva, vigencia, fase o ejecución a partir de ellos.
Tampoco se emplea la fecha del CMS como fecha administrativa. No se han analizado
los textos de todos los PDF; la cobertura es documental, parcial y sin geometría.
Cada registro tiene `publication_ready: false` y `geometry_status: unavailable`.

El manifest identifica Beas, Huelva, INE `21011`, y desactiva licencias, programación
y jitter geográfico. La actualización vuelve a obtener la instantánea completa;
no filtra por fechas ni modifica el fichero de estado. Un inventario vacío,
redirección inesperada, documentos ajenos al dominio/ruta, carpeta mezclada o
paginación detectada provocan error antes de escribir resultados.

La verificación HTTPS falló con `CERTIFICATE_VERIFY_FAILED: unable to get local
issuer certificate`, tanto con el almacén por defecto como con el del sistema.
Para la extracción live se utilizó `tls_verify: false`, declarado explícitamente
en el manifest. El adaptador verifica TLS por defecto y no reintenta de manera
silenciosa sin verificación. En esta configuración concreta no se verifica la
autenticidad TLS del servidor: queda registrado en `validation.json`. No se
modificaron almacenes de certificados ni dependencias.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_beas -v
```

Ocho pruebas correctas: agrupación y aislamiento de documentos, procedencia,
identidad estable, exclusión de formularios/anuncios, ausencia de fechas y
coordenadas inventadas, rechazo de inventario vacío, paginación y documentos
ajenos, carga del manifest y escritura a partir de la respuesta HTTP simulada.
La extracción real se ejecutó mediante `BeasAyuntamientoAdapter.backfill_proyectos`,
con la configuración del manifest y `capture_dir='evidence'`.

Evidencia local, fuera de los cuatro ficheros fuente:

- `evidence/proyectos.jsonl`: ocho registros extraídos en vivo.
- `evidence/validation.json`: contador live, URLs, limitaciones, TLS y comprobaciones documentales.
- `evidence/inventory.html`: respuesta HTML completa usada por el adaptador.
- `evidence/document-00.pdf`: primer documento NNSS 1987, HTTP 200, `application/pdf`, 56.447 bytes y firma `%PDF-` válida.
- `evidence/document-06.pdf`: certificado de aprobación inicial de modificación 06, HTTP 200, `application/pdf`, 284.500 bytes y firma `%PDF-` válida.

Se descargaron completos esos dos PDF de muestra; no se afirma que se hayan
comprobado las 97 descargas. No se ejecutaron publicación, geocodificación,
operaciones de base de datos ni despliegue.
