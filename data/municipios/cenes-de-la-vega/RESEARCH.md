# Cenes de la Vega — Granada — INE 18047

Investigación y extracción real: **8 de noviembre de 2026**. Adaptador exclusivo para este municipio. Se revisaron `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro de adaptadores y los ejemplos Chipiona y Manlleu antes de implementar.

## Fuentes oficiales y alcance

La web del Ayuntamiento, https://www.cenesdelavega.es/, enlaza su sede electrónica. La web devuelve HTTP 503 a `requests` desde este entorno, aunque el buscador permite consultar su contenido. La sede responde HTTP 200 sin identificación. La extracción utiliza exclusivamente dos inventarios públicos de esa sede:

- [8.1.1. Planeamiento urbanístico](https://cenesdelavega.sedelectronica.es/transparency/d61c3b92-0726-4754-94b3-d73d5b97fd5a/): instrumentos de ordenación general y complementarios; la rama de ordenación detallada está vacía en esta ejecución.
- [2.3. Documentos sometidos a información pública](https://cenesdelavega.sedelectronica.es/transparency/b458133f-cced-4aeb-ac4d-63a971c7f33d/): ramas finalizados/en trámite y sus años disponibles. Se recorren todas esas carpetas, seleccionando únicamente instrumentos urbanísticos identificados por su nombre.

Resultado vivo: **7 instrumentos y 105 enlaces documentales**, agrupados así:

| Instrumento | Documentos | Carpeta oficial |
| --- | ---: | --- |
| PGOU. Adaptación parcial a la LOUA de las NNSS | 13 | [PGOU](https://cenesdelavega.sedelectronica.es/transparency/d3a3c8f0-a977-42bb-b9c4-fb70c223f1b1/) |
| Revisión NNSS | 40 | [NNSS](https://cenesdelavega.sedelectronica.es/transparency/02ae8863-a661-4d45-85c1-01cd25c302ed/) |
| Estudio de detalle Vista Blanca 97, 2334001VG5123C | 1 | [Vista Blanca](https://cenesdelavega.sedelectronica.es/transparency/4b879612-4fc9-41c5-b60c-d99080d07101/) |
| Estudio de detalle Barranco del Término, 1432605VG5113A0001TT | 1 | [Barranco del Término](https://cenesdelavega.sedelectronica.es/transparency/9d290d17-7739-419a-b45c-e3a40ceac6b3/) |
| Estudio de detalle UE7 - PERI Cerro del Sol | 4 | URL canónica descubierta en la extracción y conservada en JSONL |
| Propuesta de delimitación de ATU SUB S1 Barrio de las Angustias | 5 | URL canónica descubierta en la extracción y conservada en JSONL |
| Innovación PGOU, Sector Cerro del Oro | 41 | [Cerro del Oro](https://cenesdelavega.sedelectronica.es/transparency/54554d2c-b17f-4b36-9cf4-a0e8c2fb2e68/) |

Cada registro conserva la ficha del instrumento, su inventario de origen y todos los enlaces `preview-document` de su carpeta y subcarpetas. Cada documento conserva título, carpeta temática y URL de la carpeta inmediata. Las memorias, planos y estudios ambientales de Cerro del Oro son documentos de un solo instrumento, no proyectos independientes. La identidad estable depende de la URL canónica de la carpeta; las acciones Wicket se descubren de nuevo, nunca se fijan tokens de sesión en el código.

## Paginación y límites

La sede muestra inicialmente diez elementos. Se procesa `Mostrar más` mediante GET público y cabeceras Wicket, leyendo componentes XML sin ejecutar scripts. Algunas páginas reutilizan la misma URL de acción; las páginas con múltiplos de diez documentos necesitan una petición final vacía que oculta explícitamente el control. Se comprueba ese final, se rechazan filas repetidas y se contrasta el total de documentos de cada carpeta de instrumento y subcarpeta con el contador anunciado por la sede. El límite de seguridad de paginación produce error, nunca una salida recortada. La salida se escribe solo después de completar ambos inventarios.

Cobertura **parcial y documental**, no censo de todas las obras, licencias o expedientes históricos del municipio. Se excluyen personal, padrones y fiscalidad, estudios de viabilidad de concesión de servicios, planes climáticos/deportivos, formularios y licitaciones. En la carpeta de ordenación general existe además un documento suelto [BOP19012015 PUBLICACION NORMATIVA URBANISTICA](https://cenesdelavega.sedelectronica.es/preview-document/e9a2f17c-cd16-4365-9222-9520ebc76d79), fuera de las carpetas de instrumentos: queda capturado en la evidencia de inventario, pero no se crea un instrumento adicional ni se atribuye a una carpeta sin comprobar su contenido. Los 105 enlaces corresponden exclusivamente a los siete paquetes documentales descritos.

La búsqueda también localizó anuncios oficiales del [BOJA para Cerro del Oro](https://www.juntadeandalucia.es/boja/2023/114/92) y una [evaluación ambiental de cambio de sistema deportivo a sanitario](https://www.juntadeandalucia.es/boja/2026/118/33). No se incorporan como supuestos nuevos proyectos del inventario municipal ni se usan para afirmar la situación jurídica actual. Los contratos para redactar PGOM/POU o el planeamiento de un cementerio tampoco se transforman en instrumentos ya redactados o aprobados.

## Fechas, procedencia y geometría

No se exportan fechas de acuerdo, aprobación ni publicación: los listados no ofrecen campos inequívocos. Las fechas o años dentro de títulos documentales se conservan literalmente, sin convertirlos en metadatos temporales del instrumento. La fecha de creación del archivo en la sede tampoco equivale a publicación del acuerdo. La carpeta «FINALIZADOS» describe el trámite de exposición, no demuestra aprobación definitiva o ejecución. No se infiere fase ni vigencia.

Sin coordenadas o geometría verificadas: `geometry_status: unavailable`, `publication_ready: false`. INE y provincia explícitos en cada registro. Manifest: `schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`. No se ha verificado un registro público de concesiones de licencia.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_cenes_de_la_vega -v`: **9 pruebas correctas**. Cubren alcance del parser, paginación con acción reutilizada, final vacío explícito, rechazo de duplicados y cambios de estructura, recuentos incompletos, agrupación/procedencia de anexos, exclusiones, semántica sin fechas/coordenadas y configuración del manifest.
- Ejecución real de `CenesDeLaVegaAyuntamientoAdapter(...).backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `config={'evidence_dir': 'evidence/live'}`: **7 registros**, 32 respuestas HTML/XML capturadas, contadores documentales verificados.
- Comprobación puntual de la ficha «MEMORIA I» del PGOU y su descarga: HTTP 200, `application/pdf`, firma `%PDF-` válida. Se conservaron únicamente los primeros 1024 bytes; no se ha validado el contenido completo de todos los PDF.

Evidencia local, no destinada al commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/live-run.json`, `evidence/live/source-*.txt`, `evidence/tests.txt`, `evidence/document-preview.html`, `evidence/document-check.json` y `evidence/sample-pdf-header.bin`. Las capturas contienen la navegación pública anónima; no se accedió a identificación, credenciales ni sistemas externos de publicación.
