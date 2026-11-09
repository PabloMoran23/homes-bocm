# Gorliz — INE 48043, Bizkaia

Verificación y extracción directa: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento oficial

La portada vigente es https://www.gorliz.eus/es-ES/Paginas/default.aspx.
El menú se carga por JavaScript; el código público
https://www.gorliz.eus/style%20library/kolitza/js/kolitza.js consulta la lista
SharePoint «Menu Segundo Nivel». Su endpoint público
https://www.gorliz.eus/es-ES/_api/web/lists/getByTitle('Menu%20Segundo%20Nivel')/items?$select=Title,Link
identifica Urbanismo:
https://www.gorliz.eus/es-ES/Ayuntamiento/Urbanismo/Paginas/default.aspx.
No se requiere sesión. El dominio antiguo www.gorliz.eu falla la verificación de
certificado y www.gorliz.net no resuelve; no se desactiva TLS.

Inventarios actuales, todos HTTP 200 con verificación TLS:

- [Planeamiento estructural](https://www.gorliz.eus/es-ES/Ayuntamiento/Urbanismo/Paginas/planeamiento-estructural.aspx): enlaza «PGOU en Vigor», histórico y patrimonio.
- [PGOU en Vigor](https://www.gorliz.eus/es-ES/Ayuntamiento/Urbanismo/Paginas/pgou-vigor.aspx): se descubren y recorren sus cuatro secciones, Memoria, Planos, Memoria EAE y Planos EAE.
- [Planeamiento y desarrollo](https://www.gorliz.eus/es-ES/Ayuntamiento/Urbanismo/Paginas/planeamiento-desarrollo.aspx): la columna central contiene documentos del plan especial de viviendas turísticas y el enlace al PAU A.I.E. 09. La columna derecha se titula «Histórico Planeamiento Desarrollo (No vigente)» y se excluye explícitamente.

También se revisaron Exposición pública (enlaces a boletines y aprobaciones
iniciales), Otros planes urbanísticos (ruido, accesibilidad, ZPAE), Cartografía y
la portada del portal de transparencia enlazado. No se recorren estas fuentes
como parte de la extracción. El catálogo de Open Data Bizkaia expone datos globales
orientativos y series acumuladas; no se convierten sus filas estadísticas en
proyectos. No se usan noticias, licitaciones ni formularios como expedientes.

## Resultado real y semántica

**3 instrumentos, 71 enlaces documentales**, agrupados, sin crear un proyecto por
cada plano, traducción o anexo:

| Instrumento | Documentos | Fase acreditada | Publicación | Acuerdo | Aprobación |
| --- | ---: | --- | --- | --- | --- |
| PGOU de Gorliz | 65 | «en vigor» según catálogo municipal | desconocida | desconocido | desconocida |
| Plan especial de regulación de las viviendas turísticas | 3 | formulación | 2025-06-24 | 2025-06-05 | desconocida |
| PAU A.I.E. 09 | 3 | aprobación definitiva | 2025-11-25 | 2025-11-11 | 2025-11-11 |

Los 65 documentos del dossier PGOU se distribuyen en 5 de Memoria, 39 de Planos,
12 de Memoria EAE y 9 de Planos EAE. Se conserva la modificación de ordenanzas
(artículos 200-201) incorporada en Memoria dentro del dossier PGOU; no se presenta
como una obra física adicional. No se extraen fechas de nombres de archivos ni
se atribuye al conjunto la fecha de una modificación. La etiqueta municipal
«en vigor» no verifica vigencia jurídica ni situación judicial.

Fechas y fases de los otros dos instrumentos se obtienen leyendo los boletines
PDF enlazados mediante el ejecutable **pdftotext**, ya preinstalado en el entorno;
no se instala software ni se añade dependencia Python. Si falta el ejecutable,
el texto, la identificación municipal, las fechas o el CVE esperado, falla la
extracción, conservando el JSONL anterior.

- [BOB-2025a119-(II-3784)](https://www.gorliz.eus/es-ES/Ayuntamiento/Urbanismo/plan_viviendas_turisiticas/01-bob-viviendas-turisticas-cas.pdf): acuerdo de formular el plan especial el 5 de junio, firma del 16 de junio y publicación del 24 de junio de 2025. La firma **no** sustituye la fecha del acuerdo. La suspensión de licencias publicada por un año no acredita una concesión; tampoco se afirma que continúe en 2026.
- [BOB-2025a226-(II-6823)](https://www.gorliz.eus/es-ES/Ayuntamiento/Urbanismo/pauaie09/01-anuncio-bob.pdf): aprobación definitiva del PAU el 11 de noviembre, firma del 13 y publicación del 25 de noviembre de 2025. La mención a publicación íntegra del 13 de junio es otro hito, no la publicación del acuerdo definitivo.

Cada documento mantiene título, URL y página municipal de procedencia; cada
registro mantiene su página de catálogo y, donde hay fechas, el PDF que las
sustenta. `fecha` queda nula. Los grandes planos y memorias se enlazan sin
requerir descargar cientos de MB; su contenido individual no se ha validado.
Los dos boletines sí se descargan y analizan en cada extracción.

## Cobertura, paginación y geometría

Cobertura **parcial**, limitada al dossier PGOU publicado y al desarrollo actual.
Se excluyen histórico no vigente, patrimonio independiente, planes sectoriales,
obras de otras fuentes y posibles instrumentos aún no incorporados al catálogo.
No es un inventario exhaustivo de actividad urbanística ni de licencias.

No se observó paginación activa en las páginas utilizadas. Se leen todos los
links de cada región documental, sin top-N ni corte de documentos. Si aparece
paginación reconocible, una sección PGOU nueva, un grupo de desarrollo no
reconocido o desaparece la estructura requerida, se produce un error explícito.
Los detalles PAU se descubren desde el inventario; no se fija una noticia como
seed. Las actualizaciones repiten la instantánea completa y no mantienen un
histórico de bajas. La escritura solo sustituye el fichero al completar todo.

`geometry_status: unavailable`. Los planos publicados son PDF. La página
[Cartografía de Gorliz](https://www.gorliz.eus/es-ES/Ayuntamiento/Urbanismo/Paginas/cartografia-de-gorliz.aspx)
enlaza cartografía DWG cuyo nombre menciona UTM ETRS89, pero no se ha verificado
una geometría vectorial por instrumento ni un EPSG aplicable. No se vectorizan
planos, no se geocodifica el centroide municipal y no se inventan coordenadas.
`lat`, `lon` y `geometry` quedan nulos; `publication_ready` es false.

Licencias, programación y jitter deshabilitados en el manifest. Los métodos de
licencias escriben vacío con estado `disabled`.

## Validación reproducible

Desde la raíz del repositorio:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_gorliz -v
```

**5 pruebas pasan**, sin red ni evidencia local: carga de manifest y registry,
fechas distintas y formulación frente a aprobación, agrupación documental y
exclusión del histórico, rechazo de paginación/contenido ausente/URL ajena,
dossier completo en un registro y conservación de salida ante error.

Extracción real ejecutada a través del registry (incluye anotación de la política
compartida de entidades), con esta llamada Python:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
m = load_manifest('gorliz')
m.portal.config['capture_dir'] = 'evidence/captures'
a = load_portal_adapter(m)
result = a.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

`evidence/validation.json` registra live_records=3, las 10 URL descargadas,
limitaciones, resultado de pruebas, conteos documentales y capturas con SHA256.
`evidence/proyectos.jsonl` contiene los registros reales. `evidence/captures/`
contiene las ocho páginas HTML y dos boletines PDF de la ejecución final;
otras capturas de investigación están en `evidence/`. Todo ello es local y no
se añade al código fuente. La anotación compartida devuelve categoría de entidad
`unknown` en los tres registros; no se fuerza una clasificación sin evidencia.
No se ejecutan ingestión, geocodificación, publicación ni despliegue.
