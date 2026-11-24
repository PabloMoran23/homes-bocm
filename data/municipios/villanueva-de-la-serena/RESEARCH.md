# Villanueva de la Serena — investigación portal ayuntamiento

Municipio: **Villanueva de la Serena** (`villanueva-de-la-serena`)  
Provincia: Badajoz · CCAA: Extremadura  
Código INE municipio: `06176`

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (WordPress) | https://villanuevadelaserena.es/ | Portal corporativo, transparencia, Plan EDIL/PAI |
| Plan EDIL / PAI | https://villanuevadelaserena.es/plan-edil/ | PDFs PAI, manual procedimientos, acuerdos OIL |
| Plan actuación integrado | https://villanuevadelaserena.es/plan-de-actuacion-integrado/ | Documentos PAI / Agenda Urbana |
| Agenda Urbana Española | https://villanuevadelaserena.es/agenda-urbana-espanola/ | Plan de acción local AUE (PDF) |
| Normativa urbanismo | https://villanuevadelaserena.es/portal-de-la-transparencia/normativa/normativa-sobre-urbanismo-y-medio-ambiente/ | Ordenanzas y documentación urbanística |
| Sede electrónica (STA) | https://sede.villanuevadelaserena.es/ | Trámites, tablón, carpeta ciudadana |
| Tablón de anuncios | https://sede.villanuevadelaserena.es/portal/noEstatica.do?opc_id=268&ent_id=1&idioma=1 | Tablón virtual JSON (`tablonElectronico.do`) |
| Catálogo trámites urbanismo | https://sede.villanuevadelaserena.es/sede/catalogoTramites.do?opcion=detalle&idApl=2&ent_id=1&idioma=1 | Licencia de obras, vado, primera ocupación, etc. |
| Callejero | https://villanuevadelaserena.es/callejero-de-villanueva-de-la-serena/ | Mapa callejero (sin capas urbanísticas) |
| IDE Extremadura urbanismo WMS | http://www.ideextremadura.com/CICTEX/urbanismo | Capas regionales de planeamiento (sin join expediente ayto.) |

## Cómo se listan expedientes / proyectos

- **WordPress:** páginas de transparencia y planes (EDIL/PAI/AUE) con enlaces directos a PDF en `/wp-content/uploads/`.
- **Tablón electrónico:** POST JSON a `/sede/tablonElectronico.do` con `opcion=consultar`, `opc_id=268`, `ent_id=1`, `subseccion=TABLONVIRTUAL` y **CSRFToken** de la página del tablón. Devuelve `listaDocumentos` (≈390 anuncios) y subsecciones (p. ej. `ACTAS`). Filtrado por palabras clave urbanísticas en el adapter.
- **No hay** visor de expedientes urbanísticos con listado histórico tabular ni API pública de códigos de expediente enlazable a GIS.

## Cómo se publican licencias

- **No hay** listado público de licencias concedidas con ubicación.
- Trámites **Licencia de Obras**, **Vado**, **Primera Ocupación** en catálogo sede (enlace a tramitación electrónica con login).
- El tablón puede incluir anuncios urbanísticos puntuales (BOP, medidas urbanísticas) pero no un registro sistemático de concesiones.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** WMS IDE Extremadura (`CICTEX/urbanismo`); callejero municipal WordPress; mapa web sede (`opc_id=218`) sin MapServer documentado; tablón/PDF sin georreferencia.
- **Estrategia:** ninguna capa pública enlaza polígono de parcela/expediente con anuncios del tablón o trámites. Solo planeamiento regional agregado.
- **Limitaciones:** anuncios en PDF/HTML; visor municipal no expone consulta ArcGIS/WFS por código de expediente; datos abiertos sin GeoJSON de licencias.

## Limitaciones generales

- Tablón requiere sesión + CSRF; volumen alto de anuncios no urbanísticos (filtrado en adapter).
- Trámites urbanismo requieren login (`abrirLogin`).
- Sin boletín regional asociado en cola (`bocm_count: 0`).
- El orquestador usará centroide municipal del manifest para coordenadas.
