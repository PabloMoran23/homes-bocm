# Salteras (Sevilla), INE 41085

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento oficial y alcance

La portada https://salteras.es/ contiene el widget «Planeamiento Urbanístico»,
que enlaza al inventario oficial:
https://salteras.sedelectronica.es/transparency/668172bc-1a3d-4c32-9896-3eaea200139b/

La sección se identifica como «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE /
7.3. NORMATIVA URBANÍSTICA». Respuesta HTTP 200, tabla
`TransparencyListPanel`, cuatro enlaces documentales; no se observa paginación.
El adaptador recorre todos esos enlaces. Si aparece paginación activa o una
entrada no clasificable, falla antes de reemplazar el resultado; no descarta
silenciosamente nuevas entradas.

Se obtienen **dos instrumentos**, conservando los cuatro documentos:

- Adaptación a la LOUA del planeamiento municipal: texto
  https://salteras.sedelectronica.es/preview-document/999d2260-be72-4c99-88c3-b5eda036bad7
  y planos 1–20 y 21–51:
  https://salteras.sedelectronica.es/preview-document/b243ddab-5b9f-4538-8617-e269d08580bd
  y https://salteras.sedelectronica.es/preview-document/b1b04a40-fa6e-4cd2-af4e-1a0f7cbd7196 .
- Modificación de la revisión parcial de las NNSS relativa al artículo 4.9,
  apartado 2.d), identificada por el atributo descriptivo del propio enlace.
  https://salteras.sedelectronica.es/preview-document/a8e3e2e3-c9dc-4fb1-b55c-ebbdb58daef4 .
  Es un anuncio de información pública de un instrumento concreto, no una
  licencia concedida ni una contratación. No se infiere aprobación definitiva.

Las cuatro fichas documentales se consultan también durante cada extracción,
con HTTP 200 y un iframe PDF del mismo dominio. Se guardan enlaces estables a
las fichas; las direcciones PDF son tokens temporales. Una petición adicional
al PDF de la modificación respondió HTTP 403: no se verificó su contenido
binario ni se hizo OCR. El formato PDF procede de la ficha/visor, no de una
validación de firma binaria. Se conserva esa limitación en validation.json.

## Otras fuentes examinadas y cobertura parcial

https://salteras.es/delegacion-municipal/infraestructuras-medio-ambiente-y-urbanismo/
contiene competencias, parques y noticias relacionadas; no se convierte ese
contenido genérico en proyectos. La primera petición recibió 403. La portada
y la consulta del POU fueron accesibles después, con HTTP 200.

https://salteras.es/consulta-previa-del-nuevo-plan-de-ordenacion-urbana-de-salteras/
publica una consulta previa del nuevo POU y un paquete de descarga. Es un
instrumento adicional real, fuera de la sección 7.3 y del alcance implementado.
No se presenta este scraper como inventario completo municipal ni se confunde
el texto explicativo sobre futuras fases con aprobaciones ya producidas.
No se incorporan licitaciones, impresos, ordenanzas fiscales, noticias ajenas,
fuentes privadas ni el archivo histórico no municipal de ADTA.

## Semántica y comprobación

Las fichas muestran fechas de creación en la sede (marzo/octubre de 2020).
No equivalen a fechas de publicación, acuerdo ni aprobación. El nombre del
anuncio incluye una fecha aparente del BOP; tampoco se utiliza como fecha de
acuerdo. Los registros omiten todas esas fechas, fase y coordenadas.
`publication_ready: false`, `geometry_status: unavailable`; licencias,
programación y jitter desactivados en el manifest.

Pruebas: `python -m unittest municipio.test_salteras -v`: cuatro pruebas
correctas (agrupación y deduplicación, semántica, rechazo de vacíos/formularios/
URLs ajenas/paginación, fallo atómico ante ficha sin visor y esquema manifest).
Ejecución real: `SalterasAyuntamientoAdapter.backfill_proyectos` con captura
local; **2 registros y 4 documentos**, resultado en `evidence/proyectos.jsonl`
y `evidence/validation.json`. Capturas HTML en `evidence/`. Evidencia local,
fuera de los cuatro archivos fuente solicitados. Sin publicación ni servicios
de datos externos.
