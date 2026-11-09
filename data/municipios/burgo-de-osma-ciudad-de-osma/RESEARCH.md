# Burgo de Osma-Ciudad de Osma — INE 42043, Soria

Verificación en vivo: 2026-11-09. Adaptador de cobertura parcial del inventario
municipal del Plan de Recuperación, Transformación y Resiliencia (PRTR).
Dos proyectos de obra física reales, sin inventar fechas, geometrías o licencias.
Programación deshabilitada, `geocode.jitter_missing: false`, licencias deshabilitadas.
`publication_ready: false`: no geometría de proyecto verificada.

## Fuentes oficiales e inventarios descubiertos

- https://www.burgodeosma.com/ — HTTP 200; portada oficial, dirección municipal
  en Soria; enlaza el PRTR, Urbanismo y la sede electrónica.
- https://www.burgodeosma.com/plan-de-recuperacion-transformacion-y-resiliencia/
  — HTTP 200; inventario curado, no paginado, con tres enlaces «Ver actuación»:
  alumbrado, vehículo y fotovoltaica. También enlaza accesibilidad MRR.
- https://www.burgodeosma.com/reforma-de-las-instalaciones-de-alumbrado-publico/
  — HTTP 200; objeto físico explícito: renovación de instalaciones de alumbrado
  exterior, luminarias y cuadros de mando. Presenta objeto original y modificado,
  cuatro lotes de obra, servicios técnicos y enlace al plan estratégico. Todo se
  conserva en **un proyecto**, sin convertir lotes o versiones en nuevas obras.
- https://www.burgodeosma.com/instalacion-de-generacion-electrica-renovable-para-el-autoconsumo/
  — HTTP 200; expediente PR-D5000-2022-004127: seis instalaciones solares
  fotovoltaicas (consultorio de Osma, colegio Ruiz Zorrilla, piscina Santos Iruela,
  centro juvenil, polideportivo y EDAR). Un proyecto con seis emplazamientos,
  según el objeto publicado, sin sustituir direcciones por coordenadas.
- https://www.burgodeosma.com/wp-content/uploads/2025/11/20251117_Plan-Estrategico-AP-Burgo-de-Osma-DUS5000-Fdo.pdf
  — documento enlazado por la ficha municipal de alumbrado; comprobado HTTP 200,
  `application/pdf`, cabecera PDF, 362018 bytes. Se retiene el enlace y su página
  de procedencia. El parser extrae la ficha HTML, no interpreta el contenido PDF.
- https://www.burgodeosma.com/vehiculo-electrico/ — HTTP 200; adquisición de
  vehículo, excluida del ámbito de obras físicas/planeamiento.
- https://www.burgodeosma.com/accesibilidad-mrr/ — HTTP 200; contenido de página
  consistente en imagen FOTO-ASCENSOR.jpg, sin ficha textual verificable; no se
  convierte en registro ni se infiere una obra desde el nombre de la imagen.
- https://www.burgodeosma.com/category/urbanismo/ — HTTP 200; archivo de noticias
  con cuatro páginas visibles en la consulta. No es el inventario elegido y no
  se extrae ninguna noticia: no se afirma cobertura de ese archivo ni de sus
  páginas posteriores. Formularios «Solicitud de licencia» excluidos.
- https://burgodeosma.sedelectronica.es/transparency/ — HTTP 200; inventario
  general que anuncia once documentos en «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO
  AMBIENTE». Enlaces de expansión Wicket dependientes de sesión. La prueba de
  expansión anónima devolvió cuerpo vacío: no se verificaron aquí fichas de
  planeamiento ni licencias. No se cuenta el número del menú como registros.
- https://www.burgodeosma.com/wp-json/wp/v2/pages?search=plan&per_page=100
  — descubrimiento auxiliar de la página PRTR; no usado como inventario completo
  ni como fuente de fechas de aprobación. Captura local `discovery-2.html` en JSON.

## Semántica, agrupación y límites

Cada registro procede de una ficha municipal que describe el objeto material del
proyecto y la subvención recibida. No se acepta un título de licitación aislado.
Los enlaces a contratación se guardan en `referencias_contratacion`, con la ficha
que los enlaza; no son nuevos registros ni se afirma haber leído sus expedientes.
Los PDF enlazados se guardan en `documentos` y se deduplican por URL.
La descripción conserva el texto publicado, incluso las versiones de presupuesto
y los posibles errores tipográficos, sin resolverlos mediante valores inventados.

Las fechas citadas de concesión y modificación de ayudas (por ejemplo 18/11/2022,
30/07/2025 o 05/06/2023) no acreditan aprobación de la obra. Tampoco el directorio
de subida del PDF acredita publicación. `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, `fecha_aprob` y `fase` permanecen nulos. Los textos originales
conservan su contexto. No se deduce finalización de una adjudicación.

No se extraen licencias. No se afirma cobertura completa de obras, planeamiento,
PRTR de otras administraciones o histórico municipal. No se sustituyen geometrías
por centroides, geocodificación de edificios o jitter.

## Implementación y validación

Se respeta el contrato de `municipio/adapters/portal.py` y la carga de manifest y
adaptador del repositorio; no hay cambios compartidos ni nuevas dependencias.
El backfill y la actualización descargan el índice PRTR completo y las dos fichas
seleccionadas. No hay cortes por fecha o número de registros. Los enlaces de
actuación desconocidos, ausencias de proyectos conocidos o indicadores de
paginación producen error para revisión, en lugar de truncar el resultado. Las
exclusiones conocidas son explícitas. La salida se reemplaza sólo tras validar
todas las fichas. Identidades estables derivadas de sus URL.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_burgo_de_osma_ciudad_de_osma -v`: **6 pruebas OK**.
  Cubren inventario/exclusiones, duplicados, cambios y paginación, rechazo de
  anuncio aislado, agrupación documental, fechas de ayuda no confundidas con
  aprobación, geometría nula, carga del manifest, actualización y conservación
  de salida anterior ante error.
- Extracción real mediante `load_portal_adapter(load_manifest(...))` y
  `backfill_proyectos`: **2 registros**, política de entidades `status: ok`
  (dos categorías desconocidas; no se fuerza una categoría no verificada).
- Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, HTML
  realmente descargado por el adaptador en `evidence/captures/`, PDF verificado
  y capturas auxiliares de descubrimiento en `evidence/`.

Evidencia sólo local, fuera de los cuatro archivos fuente. Sin publicación,
credenciales, instalación de software o modificaciones de infraestructura.
