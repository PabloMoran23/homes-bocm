# Torrejón de Velasco — investigación portal ayuntamiento

**Municipio:** Torrejón de Velasco (Comunidad de Madrid)  
**Slug:** `torrejon-de-velasco`  
**Fecha:** 2026-07-24  
**BOCM regional (referencia):** 14 avisos

## Resumen

Torrejón de Velasco publica anuncios administrativos en la **sede electrónica espublico gestiona**
(`torrejondevelasco.sedelectronica.es`) y dispone de web corporativa **Joomla/Gantry5**
(`ayto-torrejondevelasco.es`). No hay visor urbanístico municipal propio; la geometría de ámbitos
del PGOU está en el **SIT de la Comunidad de Madrid** (WFS público).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web corporativa | `https://ayto-torrejondevelasco.es` | Joomla/Gantry5 | Bandos, comunicados, ordenanzas, trámites |
| Tablón de anuncios | `https://torrejondevelasco.sedelectronica.es/board` | HTML tabla Wicket | Edictos, exposiciones públicas, convocatorias |
| Portal transparencia | `https://torrejondevelasco.sedelectronica.es/transparency/` | Wicket AJAX | Sección 7: Urbanismo (20 docs) — requiere sesión |
| Consulta expedientes | `https://torrejondevelasco.sedelectronica.es/expedientes` | Cl@ve / SAML | Requiere autenticación |
| SIT Comunidad de Madrid | WFS `sitcm:VPLA_V_AMBITO` | GeoJSON | 28 ámbitos PGOU (S-*, UE-*, SUNP-*, SNUP-*) |

Dominios no operativos: `www.torrejondevelasco.es` (sin respuesta DNS).

## Tablón de anuncios (`/board`)

Tabla HTML responsive con columnas:

- Documento → enlace `preview-document/{uuid}` (PDF)
- Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación (`DD/MM/YYYY`)

Ejemplos vigentes (jul 2026):

- **Instalación cámaras videovigilancia tráfico** (exp. 751/2021, obra pública)
- Padrón IBI urbana/rústica, IAE, plusvalías (fiscal, excluidos del adapter)
- Comisión programa activación 2026 (anuncio administrativo)

Paginación: botón Wicket AJAX «cargar más» (tokens de sesión; no implementado en adapter).

## Licencias

- No hay dataset abierto de concesiones con coordenadas.
- Anuncios de licencia aparecerían en tablón cuando el procedimiento sea *Licencias Urbanísticas*
  (patrón observado en municipios espublico vecinos).
- Consulta de expedientes en sede requiere Cl@ve.
- Web Joomla no expone categoría urbanismo dedicada (404 en `/urbanismo`).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Comunidad de Madrid `https://idem.comunidad.madrid/geoserver3/ows`
  — capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='TORREJÓN DE VELASCO'`.
  28 ámbitos: S-1…S-20, UE-1…UE-12, SUNP-1, SNUP-2 (polígonos EPSG:4326).
- **Estrategia:** Enriquecer proyectos cuyo título/expediente mencione código de ámbito
  (UE-*, S-*, etc.) vía query WFS; sin visor municipal ni enlace expediente→polígono.
- **Limitaciones:** Tablón sin georreferenciación; transparencia tras AJAX Wicket;
  expedientes tras login; sin ArcGIS/GeoJSON en portal del ayuntamiento.

## Limitaciones

- Tablón muestra ~10 anuncios recientes; histórico requiere paginación Wicket.
- Portal transparencia urbanismo (20 docs) no scrapeable sin tokens de sesión.
- Web Joomla: bandos/plenos sin PDFs urbanísticos indexables (solo enlace Dropbox presupuesto 2015).
- `torrejondevelasco.es` (sin guión) no resuelve.

## Estrategia adapter

1. Scrape tabla tablón `/board` (parser `data-label`).
2. Páginas informativas: tablón, consulta expedientes, portal transparencia urbanismo.
3. Geometría WFS SIT cuando el título contenga código de ámbito.
4. IDs estables: `torrejon-de-velasco-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Tablón espublico: `humanes_de_madrid.py`, `pelabravo.py`
- WFS SIT partial: `paracuellos_de_jarama.py`, `leganes.py`
