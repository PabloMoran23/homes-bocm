# Ayamonte — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://ayamonte.es | WordPress; área Urbanismo y Medio Ambiente |
| Portal PGOM/POU | https://ayamontepgom.es | WordPress dedicado al nuevo planeamiento (avance F3, participación) |
| Visor urbanístico | https://ayamontepgom.es/visor/index14.html | Leaflet + capas GeoJSON embebidas en JS |
| Sede electrónica | https://ayamonte.sedelectronica.es | espublico gestiona — tablón, trámites, transparencia |
| Tablón anuncios | https://ayamonte.sedelectronica.es/board/ | Edictos y anuncios (HTML tabla Wicket) |
| Trámites | https://ayamonte.sedelectronica.es/dossier.2 | Catálogo procedimientos (sin listado histórico licencias) |
| Urbanismo web | https://ayamonte.es/ayuntamiento-por-areas/urbanismo-y-medioambiente/ | Enlaces medio ambiente / línea verde |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | PGOM en tramitación (sin geometría WFS pública por expediente) |

## Cómo se listan expedientes / planeamiento

- **PGOM/POU:** portal `ayamontepgom.es` publica ~22 PDFs de avance (memorias, planos, anuncios BOJA) en `/documentos/avance/pgom/` y `/documentos/avance/pou/`, más instrumentos en `/rt-portfolios/` (PE casco histórico, barrio La Villa, carta arqueológica).
- **Tablón sede:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_dateFrom`; enlace a `/preview-document/{uuid}`. Actualmente pocos anuncios urbanísticos (consulta pública previa ocasional).
- **Licencias:** no hay listado histórico público; solo tablón + trámites informativos en sede.
- **Noticias:** WP REST API en `ayamonte.es` y `ayamontepgom.es` con posts sobre PGOM, EDUSI, agenda urbana.

## Licencias de obra

- Publicación vía **tablón de anuncios** sede (espublico) cuando hay edicto.
- Trámites de licencia/DR en catálogo sede (`dossier.2`) sin histórico scrapeable.
- El adapter incluye páginas informativas del tablón y trámites (patrón Vera/Lepe).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor PGOM Leaflet: `https://ayamontepgom.es/visor/index14.html`
  - Capas GeoJSON en JS estático (WGS84/CRS84):
    - `Terminomunicipal.js` — término municipal (1 polígono)
    - `Limiteurbano.js` — clasificación del suelo (14 polígonos, campo `Nombre`)
    - `ATU.js` — ámbitos ATU (19 polígonos, `COD_PD_ATU`, `NOM_PD_ATU`)
    - `Zonassr.js`, `CATEGORIASSUELORUSTICO.js`, `AGRUPACION_IRREGU.js`, `Movilidad.js`, `EQ_LOCAL.js`, `elemento_estructurantes.js`
  - Ortofoto WMS IGN (`wms-inspire/pnoa-ma`, `wms/ortosat2023`) — solo fondo, sin enlace a expediente
- **Estrategia:** descargar JS del visor, indexar polígonos por nombre/código ATU; enriquecer proyectos por coincidencia en título o añadir filas por capa; PDFs generales PGOM/POU reciben polígono del término municipal.
- **Limitaciones:** sin API por código de expediente; tablón/PDF sin georreferencia directa; SITUA no expone WFS consultable por INE 21010 en esta investigación.

## Limitaciones generales

- Sede con certificado gestionado (`insecure_ssl: true` en manifest).
- Tablón con pocos anuncios urbanísticos recientes (mayoría personal/presupuesto).
- Portal PGOM centrado en avance del nuevo instrumento (no histórico PGOU 1993-2010).
- Sin datos abiertos CKAN municipal con urbanismo.
