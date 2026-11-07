# Valverde del Camino — Huelva — INE 21072

Investigación y extracción real: 7 de noviembre de 2026.

## Fuentes oficiales e inventarios

La sede electrónica identifica al Ayuntamiento de Valverde del Camino como titular,
con teléfono 959550000 y dirección de contacto municipal. Desde su
[portal de transparencia](https://valverdedelcamino.sedelectronica.es/transparency)
se accede a [7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE](https://valverdedelcamino.sedelectronica.es/transparency/398ed7e7-2230-4bfd-969a-89d3755765a6/).

Se inspeccionaron estos inventarios actuales:

- [7.0. DOCUMENTOS EN TRAMITACION](https://valverdedelcamino.sedelectronica.es/transparency/297f7e56-036e-4dd5-81d7-c6c829be0016/): fuente implementada; seis carpetas, ocho documentos anunciados en total.
- [7.1. PLANEAMIENTO URBANÍSTICO](https://valverdedelcamino.sedelectronica.es/transparency/1b0bf67b-f9b4-4616-a107-0f3e62109506/): inventario más amplio, con 112 documentos repartidos entre NNSS, PGOU, desarrollo y otras categorías; fuera del alcance de este adaptador. Su primera vista tiene «Mostrar más».
- [7.4. OBRAS PÚBLICAS E INFRAESTRUCTURAS](https://valverdedelcamino.sedelectronica.es/transparency/88dfe41c-de3d-4d4e-a4e8-16eb0c8344da/): cuatro anuncios; los títulos de categoría no acreditan por sí mismos obras municipales. No se extraen.
- [Urbanismo de la sede](https://valverdedelcamino.sedelectronica.es/citizen-service/9ae6fd54-de11-464b-8d67-be84b1a71fca): formularios y gestiones, no registro de licencias otorgadas.

La web histórica `https://www.valverdedelcamino.eu/` y su variante sin www
agotaron el tiempo de espera desde este entorno. El dominio `.es` devolvió un
corte de conexión. Los PDF históricos encontrados en buscadores no sustituyen
un inventario recorrido ni se convierten en registros precargados.

## Resultado y agrupación

**Dos proyectos reales, siete enlaces documentales**, obtenidos en vivo mediante
el adaptador cargado desde el manifest:

1. [CA_Proyecto_Actuacion_acceso_PK2_235_HU-4100](https://valverdedelcamino.sedelectronica.es/transparency/b97b0398-4bd8-4b0d-ab8d-5ff50e69253a/): informe jurídico, informe de adecuación de uso, proyecto de actuación, síntesis y memoria técnica de calificación ambiental. Los cinco documentos forman un solo proyecto.
2. [Proyecto Actuacion Suelo Rustico CAMPING POL. 16 - PARC. 15 COTO CARRASCO](https://valverdedelcamino.sedelectronica.es/transparency/a32af2c8-45e9-4299-bc26-c207ebf8a810/): memoria y planimetría, reunidas en un solo registro.

Se visitaron y omitieron las carpetas vacías de Estudio de Detalle UE-19 y UEDP-23,
Proyecto de actuación de cortijo en finca Dehesa el Garduño y Modificación puntual
num 7 NNSS. «Obras y usos provisionales» se excluye por ser categoría genérica,
aunque anuncie un documento. No se afirma cobertura de todo el urbanismo,
todas las obras, el catálogo 7.1, ni el histórico del municipio.

Cada registro conserva título original, URL de carpeta, URL del inventario,
sección de procedencia y fichas `preview-document` con títulos individuales.
Las fichas son enlaces públicos estables; las acciones Wicket y URLs temporales
de PDF se resuelven durante la sesión y no se usan como identificadores.
El ID deriva de la URL de carpeta. La actualización sustituye la instantánea;
no implementa un histórico incremental de retiradas.

## Fechas y semántica

Son proyectos publicados como documentación en tramitación; no se afirma
concesión, aprobación, vigencia ni ejecución material. El apartado municipal no
es evidencia suficiente de una fase administrativa específica. No hay `fase`
inferida. Sin fechas de aprobación, acuerdo o publicación inventadas. La fecha
«05-may-2025 12:13:16» de la ficha del proyecto de acceso significa **creación del
documento**, no acuerdo ni publicación, y no se transfiere a esos campos. Tampoco
se interpreta el texto `2025_1019` de un título como fecha de acuerdo.

No se asignan coordenadas ni geometría; `geometry_status: unavailable` y
`publication_ready: false`. Licencias, programación y jitter desactivados en el
manifest. La clasificación compartida de entidades devuelve dos `unknown`; se
conserva esa limitación, sin alterar políticas compartidas para forzar categorías.

## Paginación y fallos

La vista 7.0 y las cinco carpetas de instrumentos visitadas no mostraron
paginación. El parser rechaza «Mostrar más», siguiente/next y `rel=next`, en vez
de aceptar una primera página incompleta. Comprueba también que el número de
documentos de cada carpeta coincida con su contador. Carpetas anidadas,
cambios de estructura, navegación sin URL estable y ausencia de proyectos
utilizables producen error antes de reemplazar el fichero de salida. Se revisan
las carpetas con contador cero para confirmar su vacío. Las categorías genéricas
excluidas se declaran en el informe de extracción.

## Verificación y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_valverde_del_camino -v
```

Siete tests correctos: agrupación y deduplicación documental, título/contador,
carpetas vacías, rechazo de formularios/anuncios, paginación y fuentes externas,
flujo del adaptador y conservación de salida previa ante contador discrepante,
manifest y licencias desactivadas. Pruebas sin dependencia de red.

La ejecución real se realizó con `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`; sin publicación,
base de datos ni geocodificación. `evidence/validation.json` contiene el recuento
real, siete URLs documentales, fuentes, exclusiones y limitaciones.
`evidence/captures/` conserva respuestas HTML de la extracción; otras capturas
de investigación están bajo `evidence/`. La ficha del proyecto de acceso se
abrió también y se descargó su PDF (HTTP 200, application/pdf, firma PDF válida;
57.765.788 bytes). Las primeras cinco páginas extraídas con `pdftotext` confirman
el proyecto del acceso a las instalaciones de Atalaya Masa Valverde desde el PK
2+235 de la HU-4100, T.M. Valverde del Camino (Huelva). Sus fechas de edición de
marzo de 2025 tampoco se consideran fechas de aprobación. El hash y capturas
constan en la validación. La evidencia queda local, fuera de los
cuatro archivos fuente entregados.
