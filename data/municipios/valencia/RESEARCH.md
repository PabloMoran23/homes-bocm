# València — investigación portal ayuntamiento

Municipio: **València** (`valencia`) — Comunitat Valenciana, provincia València. Boletín: DOGV (`dogv`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.valencia.es |
| Urbanismo | https://www.valencia.es/cas/urbanismo |
| Instrumentos en trámite | https://www.valencia.es/cas/urbanismo/instrumentos-en-tramite |
| Instrumentos aprobados | https://www.valencia.es/cas/urbanismo/instrumentos-aprobados |
| Proyectos urbanos | https://www.valencia.es/cas/urbanismo/proyectos-urbanos |
| Participación pública | https://www.valencia.es/cas/urbanismo/planes-de-participacion-publica |
| Tablón de edictos (Liferay) | https://www.valencia.es/cas/tramites/tablon-de-edictos |
| Sede — edictos | https://sede.valencia.es/sede/edictos/index.xhtml?lang=1 |
| Sede — trámites LA (obras/actividades) | https://sede.valencia.es/sede/registro/indexM.xhtml?lang=1&m=LA |
| Sede — trámites UR (urbanismo) | https://sede.valencia.es/sede/registro/indexM.xhtml?lang=1&m=UR |
| NSF tramitación urbanística | https://mhv.valencia.es/ayuntamiento/urbanismo2.nsf/fTramitacionBusquedaNW |
| Datos abiertos (CKAN) | https://opendata.vlci.valencia.es |
| Geoportal | https://geoportal.valencia.es |

## Cómo se listan expedientes / proyectos

1. **NSF Domino (`mhv.valencia.es`)** — Las páginas Liferay de instrumentos en trámite/aprobados embeben un iframe apuntando a `urbanismo2.nsf` con vista `vTramitacionWebNW`. El listado es HTML estático (`ul.listadoBusqueda > li > a`) con código de expediente y título. Cada ficha (`OpenDocument`) incluye PDFs, número de expediente y fecha de publicación DOGV.
2. **Liferay Asset Publisher** — `proyectos-urbanos` publica tarjetas con `span.enlace-title` y enlace `/cas/urbanismo/proyectos-urbanos/-/content/...`.
3. **Participación pública** — Enlaces `/-/content/planeam-planesparticipaciónpública?uid=...` con título en `bloque_titulo` dentro de la ficha.
4. **Transparencia** — Sección G.2 instrumentos de planeamiento (enlaces a las mismas rutas de urbanismo).

## Cómo se publican licencias

- **No hay dataset ni tablón estructurado de licencias concedidas** con dirección/coordenadas.
- La **sede electrónica** (`sede.valencia.es`, JSF) expone el catálogo de procedimientos:
  - Materia **LA** (Actividades y Obras de acondicionamiento): licencias/declaraciones de obra + actividad.
  - Códigos **UR.LC.*** (Licencias de edificación): nueva planta, DR obras, parcelación, etc.
- El **tablón de edictos** permite filtrar por materia UR (Urbanismo) pero requiere formulario POST con ViewState; no hay API REST pública estable.
- Estrategia del adapter: fichas procedimentales de sede (como Pozuelo) + `min_rows: 0` no aplica a licencias porque hay trámites publicados.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Geoportal València: WFS/ArcGIS `OPENDATA/UrbanismoEInfraestructuras` (PGOU calificaciones, barrios, parcelas, catálogo…).
  - CKAN: parcelas con ficha urbanística (WFS/WMS), sin campo de enlace a expediente NSF.
  - Visor cartográfico antiguo (`mapas.valencia.es/.../web_urbanismo.jsp`) devuelve 404.
- **Estrategia:** Los expedientes NSF y proyectos Liferay no exponen `objectId` ni código enlazable a capa GIS. Las capas abiertas (PGOU, barrios) no permiten join determinista expediente→polígono sin NLP/heurísticas frágiles.
- **Limitaciones:** Sin geometría por expediente en portal; el orquestador usará centroide municipal + jitter. Parcelas CKAN son catastro, no ámbito de proyecto.

## Limitaciones generales

- Sede JSF lenta (~2 min primera carga); timeout elevado en adapter.
- NSF en subdominio `mhv.valencia.es` (histórico ayuntamiento).
- Edictos urbanísticos en sede requieren sesión/POST; no integrados en v1.
- Licencias: solo trámites informativos, no concesiones con coords.
