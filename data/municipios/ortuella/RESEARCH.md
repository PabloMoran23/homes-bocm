# Ortuella — Bizkaia — INE 48083

Verificación en vivo: 2026-11-08. Un adaptador municipal; alcance parcial de
instrumentos urbanísticos publicados, sin extracción de licencias.

## Descubrimiento e inventarios oficiales

Se revisaron el contrato `municipio/adapters/portal.py`, el cargador de manifiestos,
el registro y los ejemplos de Hernani y Manlleu antes de implementar.

La portada [municipal](https://www.ortuella.eus/es-ES/Paginas/default.aspx)
no ofrece navegación útil en su HTML anónimo. Las listas públicas de navegación
SharePoint sí identifican Servicios → Urbanismo. La página del
[departamento](https://www.ortuella.eus/es-ES/Servicios/Urbanismo) describe servicios
y trámites: sus referencias a licencias **no** constituyen concesiones.

El inventario utilizado es la biblioteca pública de páginas de Urbanismo:

https://www.ortuella.eus/es-ES/Servicios/Urbanismo/_api/web/lists/getbytitle('P%C3%A1ginas')/items?$select=Id,Title,FileRef,Modified&$top=100

La consulta anónima devuelve 20 páginas y ninguna continuación en esta ejecución.
El adaptador recorre `odata.nextLink` / `@odata.nextLink` hasta agotarlas, detecta
ciclos y falla si supera el límite de seguridad; nunca acepta un resultado truncado.
Selecciona por título las tres bibliotecas revisadas y descubre sus URLs desde
`FileRef`. Las páginas hijas se siguen desde enlaces del contenido central, con
validación contra el inventario completo y detección de ciclos. Se soportan las tres
plantillas HTML municipales observadas. Una paginación HTML nueva produce error
explícito. Se escribe el resultado solamente después de completar toda la extracción.

También se examinó el catálogo oficial foral de
[planeamiento de Ortuella](https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-ortuella).
Su recurso «Datos globales de planeamiento (2023-2026)», UUID
`7b6aadde-5824-4e39-a118-bf84f3443303`, contiene estadísticas trimestrales de suelo y
vivienda, no expedientes individuales: queda excluido. No se convierten estadísticas,
formularios, noticias o anuncios de contratación en proyectos.

## Cobertura real

La ejecución a través de `load_portal_adapter(load_manifest('ortuella'))` produjo
**3 registros**, con **100 enlaces PDF únicos dentro de sus instrumentos**:

| Instrumento | Página municipal | Documentos | Páginas recorridas |
| --- | --- | ---: | ---: |
| Revisión del PGOU | [PGOU](https://www.ortuella.eus/es-ES/Servicios/Urbanismo/Paginas/PGOU.aspx) | 92 | 9 |
| Catálogo de patrimonio | [Catálogo](https://www.ortuella.eus/es-ES/Servicios/Urbanismo/Paginas/Catalogodepatrimonio.aspx) | 4 | 1 |
| Plan de acción del paisaje | [Plan](https://www.ortuella.eus/es-ES/Servicios/Urbanismo/Paginas/Planaccion_paisajeOrtuella.aspx) | 4 | 1 |

El PGOU agrupa participación pública, preavance, avances 2018/2024 y documentación
de aprobación inicial (textos y planos). «04. Documento aprobación inicial» es la
etiqueta de la biblioteca municipal, no una fecha de acuerdo ni una afirmación de
aprobación definitiva. Catálogo y paisaje tienen memorias, planos y documentación
de alegaciones/aportaciones. Los documentos no se transforman en proyectos separados.
Cada enlace conserva título, sección cuando existe y páginas de procedencia.

No se extraen la página genérica de Urbanismo, el Consejo Asesor, inspecciones,
formularios ni páginas de participación como proyectos nuevos. Tampoco se cubren
la antigua información pública ferroviaria de 2015 ni la consulta previa a la
redacción de la actuación del campo de fútbol. No hay cobertura exhaustiva de
obras, modificaciones del planeamiento, expedientes, histórico ni licencias.

## Fechas, geometría y límites

`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas: las páginas
revisadas no acreditan sus fechas legales. `source_modified_at` conserva explícitamente
la modificación de SharePoint. No se derivan fechas del nombre del PDF, del año de
un avance, de la creación de una página o de una noticia externa.

`geometry_status: unavailable`. Se enlazan planos PDF, pero no se ha identificado
geometría vectorial por expediente ni extraído geometría de los planos. No se
asignan coordenadas municipales, centroides o puntos aleatorios. Los registros
indican `publication_ready: false`. Licencias y programación están deshabilitadas;
`geocode.jitter_missing: false`.

Se verificó mediante descarga HTTP 200 y cabecera `%PDF-` una memoria por instrumento;
las tres capturas y sus SHA256 constan en `evidence/validation.json`. Los demás
PDF se conservan como enlaces de las páginas oficiales, sin afirmar comprobación
integral de disponibilidad o contenido. Las capturas HTML/JSON tienen nombre hash
de la URL; se conservan también capturas del descubrimiento. Evidencia local, fuera
de los cuatro archivos fuente solicitados.

## Validación y reproducción

Cinco pruebas pasan: alcance/procedencia de documentos, fallos de estructura y
paginación HTML, tres plantillas reales, continuación OData y agrupación con ciclo
de enlaces, fechas nulas, preservación del archivo ante fallo, manifiesto y licencias
vacías. Comando:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_ortuella -v
```

Extracción real (desde la raíz del repositorio, usando ese mismo Python):

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
m = load_manifest('ortuella')
m.portal.config['evidence_dir'] = str(Path('evidence').resolve())
a = load_portal_adapter(m)
result = a.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

`evidence/proyectos.jsonl` contiene los registros reales;
`evidence/validation.json` recoge recuento, URLs consultadas y limitaciones.
La actualización repite la instantánea completa; no usa Modified como cursor de
acuerdos ni modifica el estado de programación. No se ejecutó ningún publicador.
