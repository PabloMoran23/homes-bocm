# Eivissa — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL | Formato |
|--------|-----|---------|
| Web municipal | https://www.eivissa.es | Liferay (Clay) |
| Sede electrónica | https://eivissa.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón anuncios | https://eivissa.sedelectronica.es/board | HTML tabla `class_name`, `preview-document` |
| Bans urbanismo | https://www.eivissa.es/bans | Asset Publisher, categoría «Bans d'urbanisme» |
| PGOU 2023 | https://www.eivissa.es/pla-general-de-ordenacio-urbana-2023 | Liferay + PDFs `/documents/...` |
| Transparencia normativa urb. | https://eivissa.sedelectronica.es/transparency/c43909b2-2063-4114-bcec-56c8a94fd737/ | Enlaces externos BOIB (`extUrl`) |
| Urbanismo (área) | https://www.eivissa.es/urbanisme1 | Página informativa |
| Trámites sede | https://eivissa.sedelectronica.es/dossier | Catálogo espublico (respuesta lenta, >60s) |

## Expedientes / planeamiento

- **Tablón sede:** listado paginado en HTML (10 filas visibles en portada); columnas Expedient, Procediment, Categoria, Descripció, fecha DD/MM/YYYY. Muchas filas recientes son personal/subvenciones; filtro por palabras clave urbanísticas.
- **Transparencia 2.5 Normativa urbanística:** índice de acuerdos y modificaciones PGOU con enlaces al BOIB (eboibfront.caib.es). Fuente principal de proyectos recientes.
- **Bans d'urbanisme:** avisos de obras, restricciones estivales, interrupciones BOIB; título + fecha en catalán.
- **PGOU:** documentación aprobación definitiva 2023 (memorias, normas, estudios) en PDF Liferay.
- No hay listado público indexable de «exposición pública» por expediente (sección 7 del portal transparencia requiere navegación AJAX Wicket sin URL estable descubierta).

## Licencias de obra

- No hay dataset abierto de concesiones de licencias con coordenadas.
- El tablón puede publicar procedimientos «Llicències d'Ocupació» u otros; mayoría de entradas recientes no son licencias de obra.
- Catálogo `/dossier` incluye trámites de obres/urbanisme pero la página tarda >60s en responder desde el entorno cloud (timeout).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Web: `mapa-web` genérico, sin visor urbanístico enlazado a expedientes.
  - Geoportal CAIB / IDEIB: sin capa WFS pública localizada para expedientes de Eivissa ciudad.
  - Pollença (referencia Baleares) usa IDELMA Consell Mallorca; Eivissa (Pityuses) no comparte ese WFS municipal.
- **Estrategia:** el orquestador aplicará centroide municipio + jitter (`manifest.portal.config.centroid`).
- **Limitaciones:** publicaciones en PDF/BOIB sin georreferencia; tablón sin GIS.

## Limitaciones

- `/dossier` muy lento (posible redirect 302 tras ~15s).
- Tablón sin API JSON; filtrado heurístico de ruido (personal, mercados).
- Contenido bilingüe catalán/castellano.
