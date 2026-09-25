# Moraleja de Enmedio y Batres — investigación portal ayuntamiento

**Slug cola:** `moraleja-de-enmedio-y-batres`  
**Comunidad:** Comunidad de Madrid (`bocm`)  
**Nota:** El nombre en BOCM agrupa **dos municipios distintos** (Moraleja de Enmedio y Batres). No existe un ayuntamiento unificado; el adapter compone ambas sedes. Moraleja de Enmedio ya tiene entrada propia (`moraleja-de-enmedio`) en el pipeline.

## Moraleja de Enmedio

| Recurso | URL | Tecnología |
|---------|-----|------------|
| Sede electrónica | `https://ayto-moraleja.sedelectronica.es` | espublico gestiona (Wicket) |
| Tablón | `https://ayto-moraleja.sedelectronica.es/board` | Tabla HTML + `preview-document/{uuid}` |
| Transparencia | `https://ayto-moraleja.sedelectronica.es/transparency/` | Wicket (sección 7 Urbanismo, ~41 docs) |
| Trámites urbanismo | `https://ayto-moraleja.sedelectronica.es/citizen-service/2c9b5472-33f1-48d9-af01-ae5ae82bd19d` | Catálogo procedimientos |
| Web corporativa | `https://ayto-moraleja.es` | WordPress Avada |
| Consulta expedientes | `https://ayto-moraleja.sedelectronica.es/expedientes` | Requiere Cl@ve |

**Listado:** tablón público paginado en HTML; filtro por categoría «Urbanismo» y regex sobre título/procedimiento. Licencias concedidas no hay dataset abierto; páginas informativas de trámites + filas del tablón.

## Batres

| Recurso | URL | Tecnología |
|---------|-----|------------|
| Dominio corporativo | `https://www.batres.es` | Redirección 302 → sede electrónica |
| Sede electrónica | `https://batres.sedelectronica.es` | espublico gestiona |
| Tablón | `https://batres.sedelectronica.es/board` | Misma plantilla Wicket que Moraleja |
| Trámites | `https://batres.sedelectronica.es/dossier` | Catálogo espublico |
| Transparencia | `https://batres.sedelectronica.es/transparency/` | Wicket |
| Consulta expedientes | `https://batres.sedelectronica.es/expedientes` | Autenticación |

**Listado:** tablón con ~6 anuncios vigentes (scraping sep 2026); sin visor urbanístico propio enlazado a expedientes.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid IDEM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='MORALEJA DE ENMEDIO'` (~ámbitos PGOU) y `DS_MUNICIPIO='BATRES'` (~21 polígonos, p. ej. `APD-2 MONTEBATRES`).
  - Campo de enlace: `DS_NOMB_AMB` (códigos UE/SUNP en título del anuncio).
- **Estrategia:** Carga ámbitos WFS por municipio; enriquecimiento por código de sector en título del tablón; filas `sit_wfs` con polígono completo del ámbito.
- **Limitaciones:** Sin geometría por expediente de licencia; tablón sin coordenadas; consulta de expedientes con login. Anuncios genéricos sin código de ámbito quedan sin `geom_geojson` (geocode centroide+jitter).

## IDs y adapter

- Módulo compuesto: `municipio.adapters.moraleja_de_enmedio_y_batres`
- Batres reutiliza plantilla espublico+WFS (`municipio.adapters.batres`, IDs prefijo `moraleja-de-enmedio-y-batres-batres-…`).
- Moraleja delega en `MoralejaDeEnmedioAyuntamientoAdapter` (IDs `moraleja-de-enmedio-…`).

## Limitaciones generales

- SSL sede: certificados gestionados por espublico; `insecure_ssl` en adapters Madrid CM.
- Sin API JSON pública de licencias; dependencia de HTML del tablón.
- Entrada `batres` en cola (`pending`) duplicará Batres cuando se procese de forma individual.
