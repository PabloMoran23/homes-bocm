# Moraleja — Cáceres — INE 10128

Revisión y extracción: 2026-11-09. Comunidad autónoma: Extremadura.
La [web municipal](https://www.moraleja.es/) identifica al Ayuntamiento de
Moraleja, Plaza de España 2, 10840, Cáceres. Se evita confundirlo con Moraleja
de Enmedio, Moraleja del Vino o el barrio de Alcobendas.

## Inventarios descubiertos y alcance

Fuente del adaptador: [Tablón de anuncios — Obras y Urbanismo](https://www.moraleja.es/ayuntamiento/tablon-de-anuncios/obras-y-urbanismo)
y su [segunda página](https://www.moraleja.es/ayuntamiento/tablon-de-anuncios/obras-y-urbanismo?page=1).
Ambas responden HTTP 200. Contienen 15 anuncios en total, seis dentro del alcance.
El adaptador descubre y recorre todos los enlaces del paginador, incluidos los
numéricos y el último. Rechaza páginas repetidas, vacías, errores HTTP, cambios
de estructura y un recorrido superior a 100 páginas; nunca guarda un resultado
truncado al alcanzar el límite. El resultado se sustituye únicamente tras completar
la extracción. La actualización vuelve a leer la instantánea completa y no usa
una fecha de corte que pudiera omitir páginas antiguas editadas.

Se extraen los anuncios de Plan General Municipal, sus modificaciones puntuales
numeradas y reparcelaciones con identificador SAU. Se agrupan por instrumento,
con los anuncios originales, narrativa, fechas, identificadores Drupal y documentos
con URL de procedencia. No se cuenta un PDF como un proyecto adicional.

Resultado real: **3 instrumentos, 6 anuncios y 5 enlaces documentales**:

- **Plan General Municipal**: [anuncio de aprobación definitiva](https://www.moraleja.es/ayuntamiento/tablon-de-anuncios/obras-y-urbanismo/plan-general-municipal-aprobada-definitivamente)
  y [aprobación provisional](https://www.moraleja.es/ayuntamiento/tablon-de-anuncios/obras-y-urbanismo/aprobacion-provisional-plan-general-municipal-mayo).
  Conserva el enlace municipal original al expediente diligenciado SITEX 37410.
- **Modificación puntual n.º 5 del PGM**: [edicto municipal](https://www.moraleja.es/ayuntamiento/tablon-de-anuncios/obras-y-urbanismo/modificacion-puntual-num-5-de-la-ordenacion)
  y [publicación en DOE](https://www.moraleja.es/ayuntamiento/tablon-de-anuncios/obras-y-urbanismo/publicacion-en-el-doe-modificacion-puntual-5-del).
  Dos documentos anexos, agrupados en un instrumento distinto del PGM.
- **Proyecto de reparcelación SAU-10**: [proyecto](https://www.moraleja.es/ayuntamiento/tablon-de-anuncios/obras-y-urbanismo/proyecto-de-reparcelacion-sau-10-moraleja)
  y [publicación BOP](https://www.moraleja.es/ayuntamiento/tablon-de-anuncios/obras-y-urbanismo/reparcelacion-de-unidad-de-actuacion-sau-10).
  Dos documentos: proyecto y anuncio, sin inferir resolución de su título.

Inventarios alternativos consultados:
[Noticias de Obras y Urbanismo](https://www.moraleja.es/noticias/obras-y-urbanismo),
con paginación hasta `page=9`, contiene noticias de obras, licitaciones y duplicados
del tablón. No se extrae ese inventario ni se pretende haber recorrido sus diez
páginas. [Trámites](https://www.moraleja.es/ciudadanos/tramites) ofrece solicitudes,
no licencias concedidas. Se excluyen licitaciones, ordenanzas fiscales, solicitudes,
expropiaciones, viabilidad SAU-9 y otros proyectos de obras fuera de las familias
implementadas. El alcance es parcial y temático, no todas las inversiones del municipio.

La [ficha oficial SITEX de la modificación 5](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40907)
fue consultada y capturada como contexto: contiene trámites posteriores, incluso
publicación definitiva en DOE de 26/02/2026, ausentes en estos anuncios municipales.
No se utiliza como semilla individual ni se combina con los anuncios para atribuirles
vigencia actual. El adaptador extrae el histórico actualmente accesible del tablón,
no el registro regional completo ni una certificación de situación jurídica vigente.

## Fechas y documentos

`fecha_publicacion` dentro de cada anuncio es exclusivamente el metadato municipal.
`fecha_acuerdo` se extrae únicamente de las frases explícitas revisadas: acuerdo
definitivo de 22/12/2022 del PGM, acuerdo provisional de 12/05/2022 y acuerdo inicial
de 24/04/2025 de la modificación 5. No se propagan a un único estado o fecha del
instrumento. Las fechas de publicación en DOE/BOP no se infieren del metadato web.
No se extraen decisiones legales del contenido de los PDF.

Las dos páginas del PGM parecen haberse editado sin actualizar su fecha: muestran
17/05/2022 para un acuerdo definitivo de 22/12/2022 y 26/06/2019 para un acuerdo
provisional de 12/05/2022. Se conservan ambos valores y una advertencia por anuncio;
no se corrige ni inventa la fecha de publicación efectiva de la versión actual.

Los cuatro PDF municipales se descargaron durante la verificación: HTTP 200,
cabecera PDF y capturas locales (incluido el proyecto SAU-10, de unos 9,7 MB).
El adaptador recoge enlaces, sin descargar ni interpretar los PDF. El enlace HTTP
antiguo `sitex.gobex.es/SITEX/ptofiguras/bajarad/37410` se conserva literalmente;
no se validó su destino. El enlace de la página provisional que apunta a
`dropbox.com/upgrade` no es documentación y se excluye de `documentos`, conservando
la narrativa de la página. No se accede a cuentas ni áreas autenticadas.

## Geometría y restricciones

`geometry_status: unavailable`. Las fuentes examinadas no aportan geometría por
instrumento que se haya verificado. No se vectorizan planos ni se asigna el centro
del municipio. No se generan coordenadas. `publication_ready: false` por cobertura
parcial, estado vigente sin determinar y falta de geometría.

`licencias.enabled: false`, `schedule.enabled: false`,
`geocode.jitter_missing: false`. Los métodos de licencias escriben cero filas.
El clasificador compartido etiqueta los tres registros como `unknown`: no se
modifica ni se inventan referencias administrativas para conseguir elegibilidad.

## Validación reproducible

Desde la raíz del repositorio, con el entorno preinstalado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_moraleja -v
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m municipio.test_moraleja --live evidence
```

Cuatro pruebas sin red: familias/exclusiones; fechas y agrupación con procedencia;
recorrido completo y fallo sin sobrescribir la salida; contrato del manifest y
resolución del adaptador. Se prueban documentos ausentes y cambios de estructura.
La extracción real usa el manifest y el cargador compartido, sin orquestación ni
publicación. Evidencias locales sin incluir en los fuentes entregables:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/captures/*.html`,
`evidence/document-validation.json` y las capturas PDF. La validación contiene
`live_records: 3`, URLs consultadas y limitaciones.
