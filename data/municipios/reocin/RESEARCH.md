# Reocín — Cantabria — INE 39060

Revisión y extracción en vivo: 2026-11-08. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento oficial y alcance

1. https://ayto-reocin.com/ devuelve HTTP 200 tras redirigir a
   https://reocin.wpcomstaging.com/. La portada se identifica como página oficial
   del Ayuntamiento de Reocín y enlaza Urbanismo y la sede electrónica.
2. https://reocin.wpcomstaging.com/urbanismo/ — HTTP 200. Dentro de `main`, el
   menú `#menu-menu-urbanismo` contiene un instrumento: **Modificación Puntual
   NNSS Área 4 La Veguilla**. Se usa este inventario como entrada, sin fijar una
   noticia individual como semilla.
3. https://reocin.wpcomstaging.com/modificacion-puntual-nnss-area-4-la-veguilla/
   — HTTP 200. Inventario de publicaciones/documentos del instrumento. Actualmente
   contiene una tarjeta, «Memoria Modificación Puntual NNSS Área 4 La Veguilla».
4. https://reocin.wpcomstaging.com/2024/08/14/memoria-modificacion-puntual-nnss-area-4-la-veguilla/
   — HTTP 200. Publicación municipal que enlaza el documento técnico.
5. https://reocin.wpcomstaging.com/wp-content/uploads/2024/08/MEMORIA.pdf
   — HTTP 200, PDF real, 2.969.556 bytes, 18 páginas. SHA256:
   `fea68b54320c265bf4d19939bd69e0f938e58aa42025d0a93417903718bf5fac`.
6. https://reocin.sedelectronica.es/info.0 — HTTP 503, página de mantenimiento.
   No se pudo inventariar su tablón ni sus expedientes. No se afirma que este
   instrumento sea el único del municipio ni que cubra todo el planeamiento vigente.

La cobertura es el **menú actual de Urbanismo accesible**, que publica documentación
histórica. No constituye un histórico exhaustivo, un registro de obras ejecutadas,
un listado de expedientes actualmente en tramitación ni un registro de licencias.
La noticia de licitación de piscina en portada y los formularios de solicitud no
se usan como registros. Se obtienen **1 instrumento y 1 PDF**, no dos proyectos.

## Procedencia y semántica

El título del instrumento procede del menú oficial, su URL identifica la agrupación.
Las tarjetas descubren las publicaciones; los enlaces PDF/ZIP se extraen únicamente
del cuerpo de esas publicaciones. `documentos[].publicaciones` conserva cada URL de
procedencia y su fecha. Los adjuntos repetidos se agrupan por URL, conservando todas
las publicaciones. Cada descarga se comprueba como PDF/ZIP y se calcula su SHA256.
El ID es determinista a partir de la URL del instrumento.

`2024-08-14` es la **fecha de publicación de la memoria en la web**, leída de
`itemprop=datePublished`, y se guarda junto a esa publicación. No se convierte en
fecha de acuerdo, aprobación o concesión ni se asigna al instrumento completo.

Se revisó visualmente la portada del PDF (`evidence/memoria-page1.png`): identifica
la memoria-resumen de la modificación de las NNSS relativa a un sector del Área 4ª,
con justificación de evaluación ambiental y fecha de redacción marzo de 2017.
Contiene sellos de fases de aprobación, además de una firma de Secretaría de
31/07/2024. El extractor no interpreta sellos manuscritos ni usa la firma como fecha
de aprobación. La extracción textual del PDF recupera sobre todo sellos: no hay OCR
automático ni extracción automática de fechas jurídicas. Se retiene el original.

No se ha verificado geometría enlazada al instrumento; `geometry_status=unavailable`,
sin coordenadas, CRS o puntos aproximados. `publication_ready=false`. Al cargar el
adaptador mediante el registro compartido, la política de entidades añade
`entity_type=pendiente`, `insufficient_identity_evidence`, `activity_eligible=false`:
el registro sirve como inventario documental de planeamiento, sin forzar una
clasificación de actividad ni alterar esa política compartida.

## Comportamiento y límites del extractor

Recorre todos los instrumentos soportados del menú, todas sus tarjetas y todos los
adjuntos PDF/ZIP del cuerpo de cada publicación. No hay límite de registros ni
slice. En las páginas revisadas no existe paginación. Si aparecen controles de
paginación o carga adicional, falla explícitamente antes de sustituir el JSONL;
será necesario ampliar el recorrido antes de aceptar otra extracción. También
falla ante contenido, inventarios o adjuntos ausentes, errores HTTP, documentos
con formato inesperado o dominios fuera de los municipales verificados.

Una actualización vuelve a leer esta instantánea parcial; no interpreta ausencias
como bajas. Las licencias están deshabilitadas y sus métodos producen cero filas.
No se programa ejecución ni se geocodifican registros sin geometría.

## Validación reproducible y evidencia local

Se ejecutó con éxito:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_reocin -v
```

Seis pruebas comprueban selección de instrumentos frente a formularios/licitaciones,
deduplicación, fechas de publicación, rechazo de paginación en cada nivel,
contenido ausente/enlaces externos, agrupación de publicaciones y contrato básico
del manifest y de licencias.

Extracción real: `load_manifest('reocin')`, `load_portal_adapter(manifest)` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`adapter.config['evidence_dir']='evidence'`. Resultado: **1 registro real**.

Evidencias locales (no destinadas al commit): `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas `home.html`, `urbanismo.html`,
`la-veguilla.html`, `memoria.html`, `sede.html`, `MEMORIA.pdf`, `MEMORIA.txt` y
`memoria-page1.png`. El adaptador guarda además las respuestas de la extracción
bajo los primeros 16 caracteres del SHA256 de cada URL más extensión HTML/PDF/ZIP;
la relación de URLs queda en `validation.json` y en los registros.

Sólo se añaden los cuatro archivos fuente solicitados. Sin cambios compartidos,
dependencias, publicación, despliegues o acceso a bases de datos.
