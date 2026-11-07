# Andoain — INE 20009, Gipuzkoa

Verificado el 2026-11-07 con el runtime preinstalado. Se revisaron primero
`municipio/adapters/portal.py`, `municipio/manifest.py`, el registro de adaptadores
y los ejemplos de Hernani y Manlleu. No se modifican fuentes compartidas.

## Descubrimiento y alcance

Desde [la portada municipal](https://www.andoain.eus/es/) se descubre
[Información urbanística](https://www.andoain.eus/es/infor-urbanismo), que enlaza:

- [PGOU](https://www.andoain.eus/pgou), con documentos y planos del plan general.
- [Exposición pública](https://www.andoain.eus/es/planes-exposicion-publica), fuente implementada.
- [Aprobación inicial](https://www.andoain.eus/es/hasieran-onartua).
- [Aprobación definitiva](https://www.andoain.eus/es/planes-aprobados-definitivamente).

Todos devolvieron HTTP 200. Es importante usar `/es/`: las rutas sin prefijo de
idioma pueden devolver euskera. Son inventarios actuales de la web, aunque algunos
expedientes permanecen publicados desde hace años. Su presencia no permite afirmar
que siga abierto el plazo legal de alegaciones ni que no exista un acuerdo posterior.

Se implementa **todo el inventario de exposición pública**, actualmente dos filas,
no una lista fija de noticias. Cobertura parcial del municipio: se excluyen el PGOU,
el histórico de aprobaciones, convenios y obras no recogidas en este inventario.
No se interpretan formularios como licencias concedidas ni anuncios de contratación
como proyectos. `licencias.enabled=false`; sus métodos escriben cero registros sin red.

Los otros inventarios presentan errores que impiden usarlos sin reconciliación
adicional. Por ejemplo, en aprobación inicial, Leitzaran, Kale Nagusia y Bordaberriazpi
comparten el enlace del anuncio del PAU de Antzizu; una fila Sorabilla enlaza al detalle
de Bordaberriazpi. En aprobación definitiva, una fila Allurralde enlaza al PAU Ama
Kandida. No se corrigen estas relaciones por conjetura ni se incorporan a la extracción.
Las páginas revisadas quedan capturadas bajo `evidence/`.

## Registros y procedencia de fechas

| Instrumento | Acuerdo inicial (BOG) | Publicación BOG | «Fecha de acuerdo» del inventario |
| --- | --- | --- | --- |
| AIU-1, Kaletxiki 28-30 | 2026-02-17, resolución 407 | 2026-03-12 | 2026-03-18 |
| AIU-10 Leizaur, AD 10.2 | 2025-08-18, resolución 2130 | 2025-09-03 | 2025-09-03 |

- [Detalle Kaletxiki](https://www.andoain.eus/es/hea-1-alde-zaharra-28-30-):
  [anuncio BOG 48](https://www.andoain.eus/documents/131314/44290309/20260312_KT28_30.pdf)
  y [memoria y planos](https://www.andoain.eus/documents/131314/44290309/ED_KT_28_30.pdf).
- [Detalle Leizaur](https://www.andoain.eus/es/aiu-10-leizaur):
  [anuncio BOG 167](https://www.andoain.eus/documents/131314/42996630/20250903_ED_LeizaurInicial.pdf)
  y [memoria y planos](https://www.andoain.eus/documents/131314/42996630/2025_Martxoa_ED.pdf).

Son estudios de detalle reales, no licencias de edificación. Cada expediente genera
un único registro con ambos documentos; no se cuentan PDFs como proyectos separados.
El título y el estado del inventario se conservan. `fase=aprobación inicial` procede
del relato de la resolución en el PDF. `fecha_acuerdo` y `fecha_publicacion` se extraen
dinámicamente de su texto, no del nombre del archivo, firma del alcalde o fecha de
redacción del proyecto. `fecha_inventario` conserva la declaración de la tabla con
su etiqueta original y se marca la discrepancia. `fecha` queda nula. `date_provenance`
identifica la fuente de cada campo. No se presume aprobación definitiva.

## Comportamiento y límites técnicos

La tabla usa filas TH dentro de THEAD. Se leen todas las filas, sin límite ni corte
por fecha. IDs estables derivados de la URL municipal del instrumento, eliminando
query y fragmento. Se agrupan y deduplican documentos únicamente en la sección
sustantiva del detalle, excluyendo navegación y aviso legal. Se exige memoria/planos
y coincidencia del anuncio entre inventario y detalle.

No hay paginación en el inventario verificado. Si aparece paginación reconocible,
se falla explícitamente antes de escribir; no se acepta una primera página parcial.
También se falla ante inventario vacío, filas incompatibles, duplicados contradictorios,
detalles sin memoria, error HTTP o texto del anuncio no interpretable. Los resultados
se escriben por sustitución de archivo temporal una vez completado el recorrido.
Las actualizaciones son instantáneas completas, sin usar un cutoff de fechas; la
salida no declara eliminaciones de expedientes que desaparezcan del tablón.

El parser de PDF usa el binario `pdftotext -raw`, ya disponible en `/usr/bin/pdftotext`;
no se instala software ni se cambian dependencias. Un entorno sin dicho binario
fallará expresamente. Cambios de idioma, estructura o relato del BOG requieren revisión.

## Geometría

`geometry_status: unavailable`. Las fichas ofrecen PDF de memoria y planos, sin
geometría vectorial enlazada por expediente. No se han vectorizado los planos ni
verificado una capa GIS que identifique estos dos instrumentos. No se inventan
coordenadas, CRS, centroides ni fechas. `lat`, `lon` y `geometry` quedan nulos,
`publication_ready=false`, `geocode.jitter_missing=false`, `schedule.enabled=false`.

## Validación reproducible

Pruebas offline (4 aprobadas):

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_andoain -v
```

Cubren agrupación, IDs estables, fechas distintas de la firma y de la tabla, documentos
sustantivos, paginación, cambios de marcado, fuentes externas y conservación de la
salida previa ante un fallo. Se ejecutó además una extracción real con
`load_manifest('andoain')`, `load_portal_adapter(manifest)` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

Resultado: **2 registros vivos y 4 PDFs comprobados por descarga**, incluidos ambos
planes. `evidence/validation.json` contiene conteos, URLs, limitaciones, fechas y hashes
de las descargas; `evidence/live-captures/` contiene HTML y PDFs obtenidos por el
adaptador, y otras capturas de investigación están en `evidence/`. Son evidencias
locales, no fuentes a incorporar a Git. No se ejecutó publicación, sincronización,
orquestador ni acceso a bases de datos o credenciales.
