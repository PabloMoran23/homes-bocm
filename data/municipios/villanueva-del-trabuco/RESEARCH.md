# Villanueva del Trabuco — Málaga — INE 29097

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales e inventario

La web https://www.villanuevadeltrabuco.es/ respondió HTTP 202 sin cuerpo en la
consulta directa; no se extrajeron noticias ni formularios. La sede municipal
https://villanuevadeltrabuco.sedelectronica.es/transparency ofrece navegación
anónima con carpetas Wicket y enlaces permanentes de vista previa documental.

La carpeta municipal de Urbanismo es:
https://villanuevadeltrabuco.sedelectronica.es/transparency/6666264c-1b5f-4ab3-84ca-bd98d4719544/
Contiene 48 documentos distribuidos entre planeamiento, normativa, convenios,
calificación ambiental, medio ambiente, proyectos de actuación y adaptación LOUA.
Se extraen exclusivamente estas dos secciones:

- 6.1 Planeamiento urbanístico (22 documentos):
  https://villanuevadeltrabuco.sedelectronica.es/transparency/200f0f74-c838-4ef9-917b-a7ffce49000a/
- 6.7 Adaptación parcial de NNSS a la LOUA (4 documentos):
  https://villanuevadeltrabuco.sedelectronica.es/transparency/32c7d987-b9fe-40d3-b914-d3f67703ef6f/

El adaptador descubre ambas secciones desde Urbanismo y recorre todas sus
subcarpetas con una sesión HTTP nueva en cada ejecución. Resuelve los callbacks
Wicket actuales mediante GET ordinario y conserva las URLs canónicas de carpeta y
las URLs `/preview-document/UUID`; no almacena tokens de sesión como documentos.
Cada recuento de carpeta se contrasta con la suma recursiva de documentos. Una
paginación reconocible, bucle, inventario incompleto o documento no clasificable
provoca error antes de escribir la salida. No se establece límite de páginas.
Las carpetas NNSS actuales y PGOU están vacías; no generan registros sintéticos.

## Resultado y agrupación

La ejecución real produjo **12 instrumentos y 26 documentos**:

- Modificaciones NNSS de usos industriales, artículo 123.2.a) y renovables en suelo rústico.
- Plan Parcial UR-3 y proyecto de reparcelación UR-7 La Yesera.
- Nueva delimitación UE-17.
- Estudio de detalle de vivienda UR-4 y su modificación, como instrumentos separados.
- Estudios de detalle de calle Las Cañas, almacén Al-Andalus nº 10 y edificio plurifamiliar/aparcamientos en paseo Virgen de los Dolores nº 24.
- Adaptación NNSS a LOUA: consulta previa de 6.1 y los cuatro documentos de 6.7 agrupados.

El anuncio provisional de UR-3 se une con el certificado definitivo de su
subcarpeta. Cada documento conserva título, descripción/tooltip si existe, URL y
carpeta de procedencia. Los anuncios se incluyen únicamente como documentación
de instrumentos concretos identificados; no se convierten en obras ejecutadas ni
licencias concedidas. La agrupación usa contexto municipal y reglas explícitas;
los documentos desconocidos requieren revisión, no se descartan silenciosamente.

## Semántica y límites

Cobertura parcial del municipio: inventario documental de 6.1 y 6.7, no catálogo
completo de toda obra municipal, BOJA, BOP, contratación, noticias o licencias.
No se extraen las secciones 6.2 a 6.6: normativa y anuncios ambientales requieren
otra investigación. La ficha genérica de 6.6 «Admisión a trámite Proyecto
Actuación» no identifica por sí sola un proyecto concreto y queda fuera.

No se afirma vigencia ni aprobación global de cada instrumento. Los títulos y
descripciones documentales conservan las referencias a formulación, consulta,
avance, aprobación inicial, provisional y definitiva. `fase` queda nula: una
modificación posterior no hereda la aprobación del instrumento anterior.
`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas. Una fecha
de creación del documento no equivale a publicación ni acuerdo. Incluso la fecha
26.1.2023 en el nombre del certificado UR-3 se conserva como título documental,
sin transformarla automáticamente en fecha estructurada. No se analiza el
contenido de todos los PDF ni se derivan coordenadas. Geometría nula y
`publication_ready: false` en todos los registros.

Licencias y programación desactivadas, sin geocodificación por dispersión.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_villanueva_del_trabuco -v`.
Cubren agrupación entre carpetas, separación de modificaciones, contexto con
acentos, enlaces, recuentos, rechazo de formularios, paginación y fuentes ajenas,
y licencias desactivadas. Se ejecutó realmente `backfill_proyectos` con
`config={'capture_dir': 'evidence/live-captures'}` y salida
`evidence/proyectos.jsonl`. No se accedió a servicios de publicación ni bases de
datos. El resultado y las limitaciones constan en `evidence/validation.json`.

Se comprobó el documento oficial:
https://villanuevadeltrabuco.sedelectronica.es/preview-document/166eeb86-44b2-4b95-b0da-9791ed506f41
Su iframe respondió HTTP 200, `application/pdf`, firma `%PDF` válida; se conserva
el PDF completo del certificado UR-3 (393063 bytes). Es una muestra documental,
no una verificación jurídica del conjunto. Capturas HTML de todos los inventarios
recorridos, descubrimiento y PDF se conservan bajo `evidence/`, evidencia local
no destinada a commit.
