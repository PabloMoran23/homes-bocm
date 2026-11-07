# Castelló d'Empúries — Girona — INE 17047

Investigación y extracción real: 2026-11-07. Adaptador limitado al inventario
municipal de planeamiento, con documentos agrupados por instrumento. No es un
registro de licencias ni un inventario completo de obras públicas del municipio.

## Fuentes oficiales y alcance

- https://www.castello.cat/serveis/urbanisme/planejament-urbanistic/ — inventario
  municipal «Planejament urbanístic». El bloque General indica que no hay entradas;
  el bloque Derivat enlaza una ficha: PPU-2 Hort d’en Negre / Tià de l’Estanyol.
- https://www.castello.cat/serveis/urbanisme/planejament-en-tramit/ — inventario
  municipal con 22 fichas: modificaciones puntuales de POUM, planes parciales,
  planes especiales, PMU y proyectos de urbanización/actuación específica.
- Cada ficha enlazada se descarga y comprueba contra su título del inventario.
  Los enlaces PDF/ZIP del contenido municipal se conservan con etiqueta original,
  URL documental y URL de procedencia. «Baixa» no genera un segundo documento.
  Cada ficha es un único instrumento aunque incluya certificados, memorias,
  planos, traducciones o varias fases de tramitación.
- Ejemplos de fichas verificadas:
  https://www.castello.cat/serveis/urbanisme/planejament-urbanistic/ppu-2/ y
  https://www.castello.cat/serveis/urbanisme/planejament-en-tramit/pla-parcial-urbanistic-sector-ppu-7-mestral-1/.
  El segundo inventario contiene incluso documentación etiquetada como aprobación
  definitiva; su categoría «en trámite» no se convierte en una fase jurídica.

## Descubrimiento y exclusiones

La búsqueda del portal oficial también localizó:

- https://www.castello.cat/llicencies-dobra-major/ — instrucciones y solicitudes;
  no acredita concesiones individuales. `licencias.enabled: false`.
- https://www.castello.cat/projectes-i-activitats/ — actividades culturales y
  estudios mezclados; no se utiliza como inventario urbanístico.
- https://www.castello.cat/serveis/urbanisme/planejament-urbanistic/projecte-urbanitzacio-hort-den-negre-tia-de-lestanyol/
  — ficha de proyecto distinta del plan PPU-2. Se localizó por búsqueda, pero no
  aparece entre los enlaces de los dos inventarios actuales y queda fuera de
  este snapshot. No se fusiona un proyecto de urbanización con un plan parcial.
- https://www.castello.cat/geoportal/ — catálogo de mapas; no se ha asociado
  geometría verificable a los instrumentos extraídos.

El acceso exploratorio a `/serveis/urbanisme/` devolvió HTTP 403. Los dos
inventarios específicos sí son accesibles por HTTP 200 con User-Agent de navegador.
No se han usado credenciales ni sesiones autenticadas.

## Semántica y límites

Las fechas que aparecen en etiquetas como «Certificat», «Edicte» o «Acord» se
retienen literalmente dentro de `documentos.labels`. Sin examinar el documento
no se presupone que sean fechas de acuerdo, firma, publicación o vigencia.
`fecha`, `fecha_acuerdo`, `fecha_aprob` y `fecha_publicacion` permanecen nulas;
tampoco se infiere una fase global por la existencia de un certificado. Las
rutas de subida de WordPress no se utilizan para datar instrumentos. No se
valida el contenido ni la disponibilidad individual de cada PDF enlazado.

Los grids HTML actuales no exponen controles de paginación. El parser rechaza
explícitamente controles de paginación, carga adicional o página siguiente si
aparecen: requerirán implementar su recorrido antes de emitir otro snapshot.
No hay límite de número de fichas ni corte silencioso. Un inventario vacío,
ficha sin documentos, título incoherente, cambio de estructura, redirección
inesperada o error HTTP aborta la extracción antes de reemplazar la salida.
La normalización de mayúsculas de escapes URL por requests no se considera
una redirección (la ficha de gas contiene `%c2%b7`).

La actualización vuelve a consultar el snapshot completo: así se incorporan
nuevos anexos en planes antiguos. El ID estable deriva de la URL de la ficha;
un traslado de URL requeriría reconciliación. No se han buscado todos los
expedientes históricos ni otras fuentes de contratación, boletines o acuerdos.
No se infieren coordenadas, parcelas ni centroides. `publication_ready: false`,
`geocode.jitter_missing: false` y `schedule.enabled: false`.

## Validación reproducible y evidencias locales

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Tests: `-m unittest municipio.test_castello_d_empuries`. Cubren selección del
inventario, rechazo de formularios/estructura inválida, paginación explícita,
agrupación y procedencia documental, ausencia de fechas/geometría inventadas,
fallos de fichas, preservación de salida previa, licencias deshabilitadas,
resolución del manifiesto y normalización de escapes URL.
Resultado: 7 tests superados; extracción real de 23 instrumentos y comprobación
de IDs únicos, INE/provincia, documentos agrupados y ausencia de coordenadas.

Extracción real mediante
`CastelloDEmpuriesAyuntamientoAdapter('castello-d-empuries', {'capture_dir': 'evidence/captures'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
La evidencia local contiene `proyectos.jsonl`, `validation.json` con recuento,
URLs consultadas y limitaciones, y capturas HTML en `evidence/captures/` nombradas
por SHA-256 de la URL. No se depende de capturas externas para ejecutar tests.
Las evidencias no forman parte de los cuatro archivos de código entregados.
