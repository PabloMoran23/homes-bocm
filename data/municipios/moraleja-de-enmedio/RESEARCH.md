# Moraleja de Enmedio — investigación portal ayuntamiento

**Municipio:** Moraleja de Enmedio (Comunidad de Madrid)  
**Slug:** `moraleja-de-enmedio`  
**Fecha:** 2026-08-08  
**BOCM regional (referencia):** 6 avisos

## Resumen

Moraleja de Enmedio publica anuncios administrativos en la **sede electrónica espublico gestiona**
(`ayto-moraleja.sedelectronica.es`) y dispone de web corporativa **WordPress Avada** (`ayto-moraleja.es`).
No hay visor urbanístico municipal propio; la geometría de ámbitos del PGOU está en el **SIT de la
Comunidad de Madrid** (WFS público, 23 polígonos).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web corporativa | `https://ayto-moraleja.es` | WordPress Avada | Noticias, trámites, ordenanzas, plenos |
| Tablón de anuncios | `https://ayto-moraleja.sedelectronica.es/board` | HTML tabla Wicket | Edictos fiscales, bandos, comunicaciones |
| Portal transparencia | `https://ayto-moraleja.sedelectronica.es/transparency/` | Wicket AJAX | Sección 7: Urbanismo (41 docs) |
| Trámites urbanismo | `https://ayto-moraleja.sedelectronica.es/citizen-service/2c9b5472-33f1-48d9-af01-ae5ae82bd19d` | espublico | Catálogo procedimientos urbanismo |
| Consulta expedientes | `https://ayto-moraleja.sedelectronica.es/expedientes` | Cl@ve / SAML | Requiere autenticación |
| SIT Comunidad de Madrid | WFS `sitcm:VPLA_V_AMBITO` | GeoJSON | 23 ámbitos PGOU (UA-*, S-*) |

## Tablón de anuncios (`/board`)

Tabla HTML responsive con columnas Documento, Expediente, Procedimiento, Categoría, Descripción,
Fecha de Publicación (`DD/MM/YYYY`). Enlaces `preview-document/{uuid}` (PDF).

Contenido vigente (ago 2026): principalmente edictos fiscales (padrón IBI, IVTM, vados, plusvalías),
bandos de podas y comunicaciones genéricas. Sin licencias urbanísticas publicadas en el tablón actual.

Paginación: botón Wicket AJAX «cargar más» (tokens de sesión; no implementado en adapter).

## Licencias

- No hay dataset abierto de concesiones con coordenadas.
- Anuncios de licencia aparecerían en tablón cuando el procedimiento sea *Licencias Urbanísticas*.
- Consulta de expedientes en sede requiere Cl@ve.
- Web Avada `/tramites/` enlaza a sede; sin listado de licencias concedidas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Comunidad de Madrid `https://idem.comunidad.madrid/geoserver3/ows`
  — capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='MORALEJA DE ENMEDIO'`.
  23 ámbitos: UA-01…UA-14 (unidades de actuación), S-1.R…S-9.MX (sectores residenciales/industrial).
- **Estrategia:** Ingestar ámbitos SIT como proyectos de planeamiento con polígono WGS84;
  enriquecer anuncios del tablón cuyo título mencione código de ámbito (UA-*, S-*).
- **Limitaciones:** Tablón sin georreferenciación; transparencia tras AJAX Wicket;
  expedientes tras login; sin ArcGIS/GeoJSON en portal del ayuntamiento.

## Limitaciones

- Tablón muestra ~10 anuncios recientes; histórico requiere paginación Wicket.
- Portal transparencia urbanismo (41 docs) no scrapeable sin tokens de sesión.
- Web Avada sin sección urbanismo dedicada indexable (solo trámites genéricos).
- `/dossier` en sede redirige con latencia alta; no usado en adapter.

## Estrategia adapter

1. Ingestar 23 ámbitos PGOU desde WFS SIT (proyectos con geometría).
2. Scrape tabla tablón `/board` (parser `data-label`).
3. Páginas informativas: tablón, urbanismo sede, consulta expedientes, transparencia.
4. Geometría WFS cuando el título del tablón contenga código de ámbito.
5. IDs estables: `moraleja-de-enmedio-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Tablón espublico: `torrejon_de_velasco.py`, `humanes_de_madrid.py`
- WFS SIT + ámbitos: `venturada.py`, `valdemorillo.py`
