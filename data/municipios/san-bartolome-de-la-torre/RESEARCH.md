# San Bartolomé de la Torre — Huelva — INE 21063

## Fuentes y alcance

Investigación y extracción en vivo: 9 de noviembre de 2026. Se revisaron el
contrato `municipio/adapters/portal.py`, el cargador de manifests, el registro de
adaptadores y los ejemplos Chipiona y Hernani antes de implementar este adaptador.

Inventarios oficiales consultados:

- [Plan General de Ordenación Urbana (PGOU)](https://www.sanbartolomedelatorre.es/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/Plan-General-de-Ordenacion-Urbana-PGOU./).
  Galería con tres adjuntos: «Planeamiento Vigente en San Bartolomé de la Torre»
  (DOCX), «Catalogo de Bienes y Espacios Protegidos» (PDF) y «Normas Urbanísticas»
  (PDF). Se genera **un instrumento PGOU**, conservando los tres documentos, no
  tres proyectos diferentes. El texto extraído de las normas identifica
  expresamente el Plan General de Ordenación Urbanística de San Bartolomé de la
  Torre. El catálogo es documentación del mismo instrumento.
- [Convenios y actuaciones urbanísticas en ejecución](https://www.sanbartolomedelatorre.es/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/Convenios-y-actuaciones-urbanisticas-en-ejecucion./).
  Una entrada documental: «Convenio urbanístico para urbanizar la Fase 1 de la
  UE-18 del PGOU». Se genera **un convenio de urbanización**, conservando su PDF
  municipal como documento y enlace específico. No se afirma ejecución efectiva,
  licencia concedida ni aprobación vigente a partir del título del inventario.
- [Obras de infraestructura realizadas y aprobadas](https://www.sanbartolomedelatorre.es/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/Obras-de-infraestructura-realizadas-y-aprobadas/).
  Revisada, pero fuera de la extracción: contiene notas de prensa DOC sobre
  carretera, accesos a la torre, camino Las Bodegas, cementerio viejo, PFEA y
  Ángel Custodio, junto con listados de aspirantes a empleo. Los listados no son
  obras; las notas requerirían investigación de contenido y agrupación adicional.
  No se transforman en proyectos por su mera presencia en esta página.

Se extraen **2 registros reales y 4 enlaces documentales**, mediante lectura
actual de las dos galerías, sin precargar registros. Cobertura deliberadamente
parcial: documentos municipales accesibles, no inventario histórico exhaustivo,
ni registro autonómico completo ni garantía de vigencia jurídica actual. Las
referencias a otras modificaciones y planes dentro del DOCX no se desglosan.
Ambas galerías observadas carecen de paginación; el parser rechaza enlaces
«siguiente», `rel=next` y contenedores habituales de paginación si aparecen, para
que una ampliación del portal no produzca un resultado parcial silencioso.

## Proveniencia, fechas y límites

El DOCX se abrió como ZIP y se leyó `word/document.xml`. Describe una revisión de
normas subsidiarias, adaptación parcial y modificaciones de distintas épocas;
contiene instrucciones editoriales como «ESCANEAR» y una referencia contradictoria
a Cortegana. Por ello no se convierte su relación interna en instrumentos
individuales ni se normalizan sus fechas como si fueran las del paquete PGOU.
Las normas PDF sí contienen texto municipal identificable; el PDF del convenio
es escaneado y `pdftotext` no devolvió texto legible. No se practicó OCR.

No se asigna `fecha`, `fecha_publicacion`, `fecha_acuerdo` ni `fecha_aprob` a estos
paquetes: las referencias históricas del contenido no equivalen a una fecha
única de aprobación o publicación del conjunto. Tampoco se infieren fases,
coordenadas, concesiones de licencia, presupuestos ni recepción de obras.
`geometry_status: unavailable` y `publication_ready: false` quedan explícitos.
La política compartida, aplicada por el registro de adaptadores, clasifica el
PGOU como `pendiente` y el convenio como `documento`; ninguno resulta elegible
como actividad ni aporta evidencia de concesión. Estas anotaciones se conservan
en la evidencia sin alterar la política compartida.

Los enlaces se leen únicamente de tablas de galerías documentales y del prefijo
municipal correspondiente, evitando enlaces del pie, solicitudes de licencia y
anuncios ajenos. Se verifica cada adjunto en cada ejecución: firma `%PDF-` o ZIP
DOCX con `word/document.xml`. Se rechazan redirecciones, adjuntos HTML, galerías
vacías y desaparición de los componentes esenciales del PGOU. Toda la lectura
se completa antes de reemplazar el JSONL. El incremental realiza una lectura
completa de estas pequeñas galerías, sin cursor artificial.

**TLS:** `requests` no pudo validar la cadena del portal, ni con las CA del
runtime ni con `/etc/ssl/certs/ca-certificates.crt`. Se utiliza la opción explícita
`portal.config.tls_verify: false` solo para este host público. No hay reintento
silencioso ni desactivación global de avisos. Esto limita la autenticación de
transporte; las capturas no sustituyen una verificación TLS. La ejecución
programada está desactivada. No se consultaron credenciales ni servicios privados.

## Verificación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_san_bartolome_de_la_torre -v
```

Ocho pruebas pasan: agrupación y deduplicación del PGOU, identidad del convenio,
exclusión de formularios/empleo/enlaces ajenos, errores por rediseño o falta de
adjuntos, detección de paginación, separación de convenios distintos, conservación
del resultado anterior ante adjuntos inválidos y carga del manifest/licencias
desactivadas.

La extracción real se ejecutó mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['capture_dir'] = 'evidence/captures'` antes de cargar el
adaptador. Resultado: **2 registros**, con los cuatro adjuntos descargados y
validados. `evidence/validation.json` contiene `live_records`, URLs de inventarios
y adjuntos, limitaciones, resultado de la política y el mapa URL/captura con
hashes SHA-256. `evidence/captures/` conserva los bytes utilizados en la ejecución;
`evidence/` también contiene las páginas de investigación y textos de inspección.
Toda la evidencia es local y queda fuera de los cuatro archivos fuente.

Licencias desactivadas al no verificarse un registro público de concesiones;
`schedule.enabled=false` y `geocode.jitter_missing=false`. Sin modificaciones de
fuentes compartidas, dependencias, publicación ni despliegue.
