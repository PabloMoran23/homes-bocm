# Torredonjimeno — Jaén — INE 23087

Investigación y extracción en vivo: 7 de noviembre de 2026.

## Fuentes oficiales e inventario descubierto

La web municipal https://www.tosiria.com/urbanismo/ describe las instalaciones de Bernal; no es un inventario de proyectos. https://www.tosiria.com/legislacion-municipal/ presenta apartados de reglamentos y ordenanzas; no se convierte en actuaciones. El catálogo de trámites de https://tosiria.sedelectronica.es/info.0 tampoco acredita licencias concedidas.

El portal oficial https://tosiria.sedelectronica.es/transparency ofrece la carpeta «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (78 documentos):
https://tosiria.sedelectronica.es/transparency/343f46e8-debf-45bf-b35d-927a8df9c508/

La fuente del adaptador es su subcarpeta **PLANEAMIENTO URBANÍSTICO**, con 50 documentos:
https://tosiria.sedelectronica.es/transparency/9ec75040-0b30-44e0-b159-f4477431ab0a/

Es una selección parcial explícita. No se recorren las carpetas hermanas de estudios de detalle, proyectos de actuación, urbanización, reparcelación, planes medioambientales o calificación ambiental. «OBRAS PÚBLICAS E INFRAESTRUCTURAS» mostraba cero documentos. No se afirma exhaustividad municipal, histórica ni vigencia jurídica.

## Registros y agrupación

La ejecución real produce **2 instrumentos, 50 documentos**:

- Memoria del avance de planeamiento para identificación y delimitación de asentamientos en suelo no urbanizable: una memoria y cinco planos, agrupados en un único registro. Identidad basada en el enlace estable de la memoria; cada plano mantiene su enlace y carpeta de procedencia.
- Plan de Ordenación Urbana del Conjunto Histórico de Torredonjimeno: **44 documentos** en https://tosiria.sedelectronica.es/transparency/117e5f12-0e7d-42fb-953e-306bb1a70683/ . Incluye índice, cuatro memorias, tres documentos normativos, treinta documentos cartográficos, cuatro anexos, resumen ejecutivo y acuerdo de JGL de aprobación inicial. Las variantes de título con/sin acento tienen identificadores documentales distintos y se conservan; no se convierten en otros proyectos.

La navegación de carpetas utiliza acciones públicas Wicket con cabecera `Ajax-Location`. La cartografía tiene dos subcarpetas de 20 y 10 documentos, con páginas de diez filas y botón «Mostrar más». El adaptador aplica exclusivamente los componentes XML, sin ejecutar JavaScript; sigue el botón hasta desaparecer, incluso cuando se reutiliza la misma URL de consulta. Comprueba los recuentos documentales recursivos contra los publicados en cada carpeta. Un bucle, cambio estructural, discrepancia o límite de seguridad provoca error antes de sustituir la salida; nunca se entrega una página truncada como completa.

## Procedencia y semántica

Los enlaces `/preview-document/<uuid>` son fichas documentales públicas estables; no se guardan acciones Wicket temporales como enlaces de documentos. Cada documento conserva `titulo`, `url` e `inventory_url` de su carpeta concreta. Las identidades de instrumento no dependen del orden ni de los títulos cambiantes.

Comprobación puntual del acuerdo de JGL:
https://tosiria.sedelectronica.es/preview-document/f54d3a59-2638-4a56-b34d-688b56c54bec

La ficha respondió HTTP 200 y declara PDF y «Fecha de creación 20-mar-2026 12:20:02». Se comprobó también HTTP 200 y firma `%PDF-` del inicio del PDF enlazado, guardando solo 1024 bytes. **Fecha de creación no es fecha de acuerdo ni de publicación**. No se descarga ni interpreta todo el contenido de los 50 documentos.

Como contraste de descubrimiento, el BOJA publica un anuncio municipal:
https://www.juntadeandalucia.es/boja/2026/62/55

Su boletín es de 31/03/2026 y el anuncio está fechado 16/03/2026; no se usan esas fechas como acuerdo. No se añade otro registro por este anuncio del mismo instrumento ni se deduce aprobación definitiva de la existencia de un acuerdo inicial. El adaptador no extrae fechas, fase, geometría ni coordenadas; `publication_ready: false` y `geometry_status: unavailable`. No convierte formularios ni anuncios de contratación en licencias/proyectos. Licencias, ejecución programada y jitter desactivados en el manifest.

## Verificación reproducible y evidencia local

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`

Pruebas: `PYTHONDONTWRITEBYTECODE=1 /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_torredonjimeno -v` — **9 pruebas correctas**. Cubren identidad y manifest, enlaces oficiales, agrupación, procedencia, paginación XML completa, callback reutilizado, fallo por recuento/bucle, tabla ausente, estabilidad de ID y ausencia de fechas/fases/posiciones inventadas.

Ejecución real mediante `load_manifest('torredonjimeno')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. La configuración opcional `capture_dir: evidence/captures` conserva las respuestas HTML/XML gzip e índice de URL/captura; solo realiza GET públicos. También pasa la anotación compartida de entidades del registry, sin modificar código común. Su clasificación queda desconocida para ambos instrumentos: no se fuerzan categorías del catálogo compartido.

Evidencia local, fuera de los cuatro archivos fuente: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/live-result.json`, capturas con índice, ficha del acuerdo y comprobación del PDF. Las limitaciones incluyen cobertura de una sola carpeta, ausencia de registro de licencias verificadas, fechas y geometría no extraídas, y comprobación binaria puntual de un documento. `update_proyectos` vuelve a generar la instantánea actual; no promete un histórico incremental.
