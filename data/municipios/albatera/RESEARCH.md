# Albatera — INE 03005, Alicante

Verificación y extracción real: 7 de noviembre de 2026. Runtime:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuente oficial

La web municipal https://albatera.es/ enlaza la sede oficial
https://albatera.sedelectronica.es/. Su portal público de transparencia
https://albatera.sedelectronica.es/transparency muestra la sección
«7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (61 documentos).
La navegación Wicket devuelve `Ajax-Location` con las carpetas persistentes:

- Sección 7: https://albatera.sedelectronica.es/transparency/e4376ef0-94ca-4ca7-8390-e65e00447a6b/
- Sección 7.1, inventario implementado: https://albatera.sedelectronica.es/transparency/350eaa4d-01c2-4fa7-9ce4-d6961986f094/

La sección 7.1 contiene 41 documentos: normas subsidiarias originales (22),
modificación 1 de NNSS (2), modificación 2 (1), texto refundido compartido de
modificaciones 1 y 2 (1), plan parcial sector 3 polígono industrial Mos del Bou
(9), modificación del plan parcial industrial sector 2 (6). La modificación 3
posee una carpeta vacía (0), que no genera registro.

El adaptador descubre las carpetas desde el inventario y resuelve sus acciones
en una sesión HTTP pública. Las respuestas XML Wicket contienen componentes
HTML en CDATA: se analizan como datos, sin ejecutar JavaScript. Se recorren
todos los botones «Mostrar más», también en la carpeta NNSS de 22 documentos
(10 + 10 + 2). El botón puede conservar el mismo token entre páginas; se
comprueba progreso mediante identificadores documentales y se rechazan
repeticiones, respuestas inesperadas y discrepancias con los recuentos.
Cualquier fallo impide escribir un resultado parcial nuevo.

## Registros y semántica

Resultado real: **5 instrumentos, 41 documentos únicos**. Cada carpeta con
documentación produce un registro con todos sus enlaces de vista previa,
nombres de archivo cuando se exponen y procedencia. El texto refundido de
modificaciones 1 y 2 se enlaza en ambos instrumentos, con relación explícita;
no genera un sexto proyecto. Los planos y anexos permanecen agrupados.

La vista previa de la memoria NNSS respondió HTTP 200 y muestra formato PDF,
un iframe de previsualización y metadatos documentales. Su fecha de creación
16-abr-2019 corresponde al documento electrónico; no es una aprobación del
planeamiento. El nombre del anuncio del BOP de 17 marzo 1990 se conserva como
etiqueta documental sin convertirlo en fecha de acuerdo. No se extrae el
contenido íntegro de los PDF ni se infiere fase, vigencia o aprobación definitiva.
Fechas de publicación/acuerdo/aprobación y geometría quedan nulas;
`publication_ready=false`. Los enlaces persistentes de vista previa evitan
fijar tokens temporales de descarga.

## Cobertura parcial y exclusiones

Se implementa únicamente 7.1, no el conjunto de obras municipales, otras
subsecciones ambientales, actas o anuncios históricos. Es una instantánea
actual del inventario público, no un registro exhaustivo de expedientes.
https://albatera.es/ayuntamiento/modelos-de-instancias/ contiene solicitudes,
declaraciones responsables y modelos vacíos: no son licencias concedidas.
Las noticias municipales y anuncios de contratación no se usan como registros.
No hay registro de licencias concedidas verificado: licencias desactivadas.
Programación desactivada y `geocode.jitter_missing=false`.

## Validación reproducible y evidencia local

`PYTHONDONTWRITEBYTECODE=1 /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_albatera -v`

Pruebas de paginación XML, bloqueo ante falta de progreso, agrupación de
anexos y documento compartido, exclusión de carpeta vacía, recuentos
incompletos y carga del adaptador desde el manifest.

Ejecución HTTP real de `AlbateraAyuntamientoAdapter.backfill_proyectos`, sin
base de datos ni publicación. `evidence/proyectos.jsonl` contiene los cinco
registros; `evidence/validation.json` contiene `live_records`, `source_urls`,
limitaciones, recuentos y hashes de capturas comprimidas en `evidence/captures/`.
Las URL de acciones Wicket son evidencia de la sesión, no identificadores de
proyecto. No se utilizan credenciales. Las capturas incluyen únicamente páginas
públicas. Evidencia local excluida de los cuatro archivos fuente solicitados.
