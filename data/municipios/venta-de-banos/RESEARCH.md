# Venta de Baños — INE 34023, Palencia

Verificación en vivo: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales descubiertas

- Web municipal: https://ventadebanos.es/ enlaza su sede y portal de transparencia.
- Inventario de transparencia: https://ventadebanos.sedelectronica.es/transparency
- Categoría 7, Urbanismo, obras públicas y medio ambiente:
  https://ventadebanos.sedelectronica.es/transparency/c1627267-433e-432c-abd6-95e4533122e2/
- Inventario 7.1, Planeamiento urbanístico, **143 documentos**:
  https://ventadebanos.sedelectronica.es/transparency/52b4b1a2-d309-41b9-b982-15174fe6423e/
- Tablón actual, inspeccionado como fuente alternativa:
  https://ventadebanos.sedelectronica.es/board
  Contiene también anuncios presupuestarios, convocatorias y otros asuntos ajenos al
  alcance; no se trata como inventario de proyectos ni de licencias concedidas.
- https://ventadebanos.es/municipio/urbanismo/ devuelve la portada; el endpoint
  público https://ventadebanos.es/wp-json/wp/v2/pages/31752 confirma contenido vacío.
  No se extrae un supuesto proyecto desde ese enlace de navegación.

La categoría 7.4 Obras públicas e infraestructuras anuncia cero documentos.
Se eligió el inventario de planeamiento, con expedientes y documentos técnicos,
frente a noticias o anuncios de contratación. No se consulta el perfil de contratante.

## Cobertura y agrupación

Extracción completa del inventario seleccionado: **18 instrumentos**, **143 enlaces
documentales**. Incluye 12 instrumentos de planeamiento y seis proyectos de
normalización y urbanización (Av. Castilla y León, Jorge Manrique, Segovia,
Recesvinto, Zamora y Horacio Miguel). El planeamiento incluye modificaciones del
PGOU (358/2017 y 130/2023), estudios de detalle SIRO (287/2016) e ICE (1020/2017),
Plan Parcial SUR-SE 07 «Huerta de los Maristas» (1075/2022), Casado del Alisal 14,
AA-UN-18, Tren Rápido/Tren Talgo, SUNC SE 03 y otros estudios de detalle del listado.

Cada carpeta delimita un instrumento. Se conservan todos los documentos y su
`source_page`, incluidos informes, memorias, planos y publicaciones, sin convertir
cada anexo en un proyecto. Las carpetas diligenciadas de AA-UN-18 y Tren Rápido/
Tren Talgo se agrupan con sus versiones originales, conservando ambas URLs.
Los dos planos sueltos de SUR-SE 07 se integran con el plan parcial; su carpeta
vacía no genera otro registro. El anuncio suelto de aprobación definitiva del
estudio de detalle Casado del Alisal 14 identifica un instrumento por título y
emplazamiento. No se inventa un número de expediente para él.

El adaptador descubre las URLs de las categorías desde la raíz y resuelve los
links Wicket mediante la cabecera `Ajax-Location`. Recorre «Mostrar más» en la raíz
y en cada carpeta hasta su desaparición. Analiza los componentes XML devueltos;
no ejecuta JavaScript. Admite acciones de paginación reutilizadas por Wicket y
exige entradas nuevas. Contrasta los documentos con el recuento de cada carpeta
y con los 143 de la categoría padre. Ciclos, duplicados, discrepancias, respuestas
vacías, enlaces inesperados y nuevos documentos sueltos sin agrupación conocida
provocan error. El límite defensivo de páginas produce error, nunca truncamiento.

## Fechas, estados y procedencia

`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas: el
inventario no expone esas fechas de forma estructurada. Las fechas en títulos de
boletines, informes o metadatos de creación documental no se trasladan a fechas
del proyecto. La hora actual de la sede tampoco es una fecha de publicación.
La fase «aprobación definitiva» solo se recoge cuando aparece explícitamente en
el título del instrumento (Casado del Alisal) o en su documento (PGOU Patinter).
No se infiere aprobación por la presencia de un estudio diligenciado.

Se verificaron vistas públicas de documentos reales, con formato PDF y metadatos,
para Av. Castilla y León, Casado del Alisal y SUNC SE 03; capturas en `evidence/`.
Los PDFs de muestra se conservan localmente. La portada del proyecto AA NU30
identifica al Ayuntamiento como promotor y al arquitecto municipal como redactor.
El PDF de Casado del Alisal distingue acuerdo de 19/01/2022, publicación en BOCyL
de 28/01/2022 y expediente 563/2021, frente a creación en la sede de 29/09/2022.
Esta comprobación manual se conserva como evidencia; esos datos del contenido PDF
no se incorporan como constantes al scraper del inventario. Los enlaces emitidos son las vistas
canónicas `preview-document/<UUID>`; no se persisten tokens temporales de descarga.

## Limitaciones y geometría

Cobertura parcial del municipio: se cubre íntegramente el inventario 7.1 publicado
a la fecha de consulta, sin afirmar exhaustividad histórica ni vigencia jurídica
de todos los instrumentos. No se recorren actas plenarias, registros privados,
contratación ni boletines provinciales/autonómicos como inventarios adicionales.
No se extraen fechas, presupuestos o geometrías del contenido de los PDF.

geometry_status: unavailable

No se ha verificado una capa vectorial pública enlazable a estos expedientes.
Los planos PDF no se georreferencian ni vectorizan. Coordenadas y geometría nulas,
`publication_ready: false`, sin centroides ni desplazamientos artificiales.
No existe un registro de licencias concedidas verificado en esta investigación;
licencias, programación automática y jitter quedan deshabilitados.

## Validación reproducible

Desde la raíz del repositorio:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_venta_de_banos -v
```

Siete tests cubren esquema/carga del adaptador, parser de carpetas/documentos,
XML Wicket, paginación completa con acción reutilizada, detección de estancamiento,
recuentos incompletos, agrupación de versiones y planos, y ausencia de fechas
inferidas. Extracción real a través del adaptador del manifest:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
manifest = load_manifest('venta-de-banos')
manifest.portal.config['evidence_dir'] = str(Path('evidence/captures').resolve())
adapter = load_portal_adapter(manifest)
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Resultados locales: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/tests.txt`, HTML/XML del inventario y muestras documentales. Evidencias
fuera del conjunto de cuatro archivos fuente; sin publicación ni ejecución de
otros pasos del pipeline.

La ejecución adicional mediante el registro compartido anota cinco expedientes con
referencia explícita y deja 13 entidades pendientes por identidad insuficiente para
sus reglas genéricas (`entity_policy.status: adapter_incident`,
`reason_code: unknown_entity_spike`). Se conserva íntegro este resultado en las
evidencias; no se inventan referencias para eludirlo. Los 18 instrumentos tienen
títulos y documentos oficiales verificables, pero esta clasificación y la ausencia
de geometría impiden considerarlos listos para publicación. Requieren revisión
independiente; `accepted: false`. No se modifica la política compartida.
