# Sanlúcar la Mayor — Sevilla — INE 41087

Investigación y extracción real: 2026-11-07. Adaptador exclusivo de este municipio.

## Fuente oficial y descubrimiento

El [portal de transparencia del Ayuntamiento](https://transparencia.sanlucarlamayor.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-e-Innovaciones-de-Planeamiento/) publica el inventario «Plan General de Ordenación Urbana (PGOU) e Innovaciones de Planeamiento», sección «PGOU del Municipio». La página identifica al Ayuntamiento de Sanlúcar la Mayor, Sevilla. No se utilizan portales de otros municipios con nombres parecidos.

Inventario consultado en vivo, incluyendo todas sus páginas:

- [Página 1](https://transparencia.sanlucarlamayor.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-e-Innovaciones-de-Planeamiento?pagegalleryfiles-1-1=1)
- [Página 2](https://transparencia.sanlucarlamayor.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-e-Innovaciones-de-Planeamiento?pagegalleryfiles-1-1=2)
- [Página 3](https://transparencia.sanlucarlamayor.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-e-Innovaciones-de-Planeamiento?pagegalleryfiles-1-1=3)
- [Página 4](https://transparencia.sanlucarlamayor.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-e-Innovaciones-de-Planeamiento?pagegalleryfiles-1-1=4)

El [anuncio municipal del avance del PGOM](https://www.sanlucarlamayor.es/es/actualidad/noticias/APROBACION-DEL-DOCUMENTO-DE-AVANCE-Y-DOCUMENTO-INICIAL-ESTRATEGICO-DEL-PLAN-GENERAL-DE-ORDENACION-MUNICIPAL-DE-SANLUCAR-LA-MAYOR/) muestra fecha de publicación 27/11/2025. Es una fuente adicional descubierta, fuera del inventario extraído. No se convierte en otro proyecto ni se toma su fecha de publicación como acuerdo. La existencia de ese anuncio evidencia que el inventario no garantiza la última fase de cada instrumento.

## Cobertura obtenida

39 entradas documentales en cuatro páginas; 28 enlaces PDF conservados en **10 registros**:

| Instrumento identificado | Documentos |
| --- | ---: |
| Normas Subsidiarias 1982 | 1 |
| PERI Encinares de Sanlúcar | 1 |
| MP Ranchos del Guadiamar | 1 |
| PP15-La Marquesa | 1 |
| PGOU, adaptación LOUA | 13 |
| Innovación nº 5, Cementerio | 2 |
| Innovación nº 6, Conjunto Solúcar | 1 |
| Innovación nº 7 | 4 |
| Innovación nº 3 | 3 |
| PGOM, documento Fase1-PT y PPC | 1 |

La clasificación se basa en los títulos explícitos del inventario. Cada registro conserva en `documentos` el título literal, URL de descarga y página de procedencia. Las memorias, planos, correcciones y estudios ambientales de la misma familia se agrupan. No se interpreta cada plano como un proyecto independiente. La URL principal es un documento concreto del grupo; `inventory_url` apunta al listado. No se infiere el significado de PT/PPC, el ámbito de innovaciones sin nombre explícito, ni aprobación de documentos.

Se excluyen 11 entradas: ocho láminas de determinaciones urbanas, una de patrimonio arquitectónico sin atribución explícita a un instrumento, una ordenanza y una zonificación acústica. Estas exclusiones constan en las limitaciones y las capturas preservan sus enlaces. No son un registro público de licencias concedidas.

## Semántica y límites

Cobertura parcial del inventario de planeamiento municipal actualmente accesible; no censo de todas las obras públicas, proyectos ni licencias, ni seguimiento de acuerdos. PGOM solo contiene el documento de fase 1 del listado, cuyo nombre incluye 29-04-2024. Ni esa fecha ni «1982» se convierten en fechas de acuerdo, aprobación o publicación. No se generan campos de fechas, fase, coordenadas ni geometría. `publication_ready: false`, `geometry_status: unavailable`; licencias, ejecución programada y jitter desactivados en manifest.

No se verifica la vigencia jurídica o aprobación ni se extrae el texto completo de los PDF. Se verificó una muestra documental del PGOM: respuesta HTTP 200, application/pdf, firma `%PDF-`; se guardaron solo los primeros 4096 bytes. Los demás documentos conservan enlaces oficiales sin afirmar descarga o validación individual.

## Implementación y validación

Se inspeccionaron `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro y los ejemplos de Chipiona y Hernani antes de implementar. Se usa el contrato municipal existente sin modificaciones compartidas o dependencias nuevas.

El crawler descubre todos los enlaces de paginación del propio inventario y sigue los nuevos hasta agotarlos, sin límite que corte silenciosamente. Verifica el marcador de página actual, rechaza páginas repetidas, huecos, redirecciones inesperadas y cambios de estructura. Títulos nuevos no reconocidos producen error para revisión. El resultado se escribe al finalizar correctamente; una descarga fallida no sustituye la salida anterior. `update_proyectos` vuelve a consultar el inventario completo, sin pretender un histórico incremental de bajas o acuerdos.

Comando ejecutado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sanlucar_la_mayor -v
```

Cinco pruebas correctas: agrupación y aislamiento de documentos, exclusiones, fechas ausentes, paginación, respuesta vacía/cambiada, enlaces externos, consulta paginada ignorada, recorrido de páginas, preservación de salida ante errores y carga real del manifest/adaptador.

Ejecución en vivo mediante `load_portal_adapter(load_manifest('sanlucar-la-mayor')).backfill_proyectos(...)`, usando el runtime preinstalado y captura local configurada. Resultado: 10 registros; la política compartida de entidades informa 10 clasificaciones conocidas y estado ok.

Evidencia local (no destinada a commit): `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/inventory-1.html` a `inventory-4.html`, `evidence/pgom-pdf-prefix.bin`. Validation contiene hora UTC real, URLs consultadas, recuentos, limitaciones y comprobación de PDF. Sin acceso a credenciales, bases de datos ni publicación.
