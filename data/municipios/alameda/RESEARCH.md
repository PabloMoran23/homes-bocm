# Alameda (Málaga), INE 29001

Investigación y ejecución real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron `municipio/manifest.py`, `municipio/adapters/portal.py`, los adaptadores y manifests de Chipiona y Manlleu y la investigación de Chipiona antes de implementar.

## Descubrimiento de las fuentes oficiales

La web https://www.alameda.es/ respondió HTTP 202 sin contenido utilizable. La sede municipal https://alameda.sedelectronica.es/transparency sí ofrece un inventario público anónimo. Su pie identifica Alameda y el teléfono municipal 952710025. Los enlaces de carpetas se resuelven mediante callbacks Wicket: una consulta de navegación devuelve la cabecera `Ajax-Location` con una URL de carpeta estable. No se usa autenticación ni se ejecuta JavaScript remoto.

Inventario de urbanismo:
https://alameda.sedelectronica.es/transparency/a8a3493d-17d0-420a-8f9d-79ba47b6524d/

En la consulta observada contiene 52 documentos distribuidos entre planeamiento (42), normativa urbanística (6), obras públicas (4), y dos categorías vacías. Son cantidades de documentos, no de proyectos. Las capturas de descubrimiento están en `evidence/urbanismo.html`, `7.1..html`, `7.3..html` y `7.4..html`.

## Cobertura implementada y agrupación

Se extraen exactamente dos instrumentos nominados; las URLs de carpeta son sus identidades estables, sin copiar registros precargados:

1. **PLAN BÁSICO DE ORDENACIÓN MUNICIPAL (PBOM)**:
   https://alameda.sedelectronica.es/transparency/6dc62266-2848-4ce4-bbda-75c6a1118b62/
   Carpeta publicada bajo Planeamiento Urbanístico. Once documentos: seis tomos, tres conjuntos de cartografía, un decreto de participación ciudadana y otro de consulta del avance. Todos se agrupan en un registro; los decretos no son proyectos independientes. Se conserva cada título, URL pública de previsualización y descripción disponible.
2. **PLAN MUNICIPAL VIVIENDA Y SUELO**:
   https://alameda.sedelectronica.es/transparency/1d04d624-dd6e-4621-864f-ed03abd91459/
   Carpeta publicada bajo Normativa Urbanística. Seis documentos: expediente administrativo, resumen y cuatro archivos de memoria. Se agrupan como un único instrumento, sin interpretar los prefijos numéricos de archivo como actuaciones distintas.

La cobertura es parcial y documental. No se considera este inventario un registro exhaustivo ni exclusivamente reciente. Quedan fuera la documentación gráfica ALA_AP_AD (28 documentos), su memoria/anexo (2), el documento técnico UR 3 A (1) y los cuatro decretos históricos de obras. La identificación y atribución de esos documentos a instrumentos/obras concretos requiere investigación adicional. No se convierten cada plano, una certificación abreviada o una noticia en un proyecto. Las demás secciones de transparencia y el tablón no están cubiertos. Formularios de solicitud o declaraciones responsables no acreditan licencias concedidas; licencias están desactivadas.

## Paginación y errores

La sede entrega diez documentos por tanda en el PBOM. El scraper sigue el botón **Mostrar más**, solicita XML Wicket dentro de la misma sesión HTTP anónima y aplica sus componentes HTML. La segunda tanda aporta el decreto `DECRETO 2025-0482 [CONSULTA AVANCE PBOM]`. Solo después de desaparecer el botón se analiza la carpeta completa. El PMVS muestra sus seis documentos sin paginación. No hay un límite silencioso: callbacks repetidos, falta de progreso, XML inesperado, redirecciones o superar la protección de 100 tandas provocan error antes de escribir la salida. Se rechazan cambios de carpeta, subcarpetas inesperadas, enlaces de documento ajenos y categorías sin documentos técnicos. Las actualizaciones refrescan la instantánea completa; no se inventa un cursor incremental.

## Procedencia y semántica

Cada registro conserva `inventory_url` y `documentos` con enlaces persistentes `/preview-document/UUID`. Los enlaces PDF de visor son temporales y no sustituyen esas referencias. No se atribuyen fechas de acuerdo a partir de números de decreto, fechas del CMS, años de archivo o momento de captura. `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas; tampoco se infiere una fase desde el tipo del plan. La publicación en la carpeta no demuestra vigencia ni aprobación definitiva.

Se descargaron dos muestras completas desde sus visores municipales: `PBOMA TOMO I` (8.389.938 bytes) y `TomoIIIResumen` (18.646.351 bytes). Ambos respondieron HTTP 200, `application/pdf` y firma `%PDF-`. Los archivos están en `evidence/pbom-sample.pdf` y `evidence/vivienda-sample.pdf`; las páginas de visor también están capturadas. La portada y el índice del PBOM identifican expresamente Alameda, **Avance, junio 2025**, Tomo I, Memoria Informativa; ese mes de redacción no se convierte en fecha de aprobación. La portada escaneada del segundo PDF se revisó visualmente (`evidence/vivienda-cover.png`): identifica **Plan Municipal de Vivienda y Suelo, Alameda, Tomo III, Resumen Ejecutivo, junio 2018** y contiene diligencia municipal. El adaptador no analiza ni transcribe las fechas de esa diligencia. La revisión confirma que los dos conjuntos corresponden a instrumentos reales del municipio, no a formularios ni anuncios de contratación.

Sin coordenadas ni geometrías verificadas: valores nulos, `geometry_status: unavailable`, `publication_ready: false`. El manifest desactiva `schedule.enabled` y `geocode.jitter_missing` e identifica explícitamente Andalucía, Málaga e INE 29001.

## Verificación reproducible

Pruebas offline:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_alameda -v
```

Siete pruebas correctas: agrupación/deduplicación y aislamiento entre instrumentos, semántica sin fechas fabricadas, rechazo de formularios/vacíos/carpetas erróneas/enlaces ajenos, consumo de la segunda tanda XML, fallo ante paginación estancada sin sobrescribir una instantánea previa, fallo de XML inesperado y licencias desactivadas.

Extracción real utilizada:

```python
from pathlib import Path
from municipio.adapters.alameda import AlamedaAyuntamientoAdapter
adapter = AlamedaAyuntamientoAdapter(config={'capture_dir': 'evidence'})
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Resultado: **2 registros reales, 17 documentos**. `evidence/validation.json` recoge `live_records`, `source_urls`, limitaciones y verificaciones PDF. Las capturas exactas de la extracción son `alameda-source-01.html`, `alameda-source-02.xml` y `alameda-source-03.html`. Evidencia local, no destinada a commit. No se han modificado fuentes compartidas ni dependencias; no se ha publicado, desplegado ni accedido a bases de datos.
