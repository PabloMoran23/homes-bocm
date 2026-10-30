# Ames — investigación portal ayuntamiento

Municipio: **Ames** (`ames`) — Galicia, provincia A Coruña.  
INE: **15002**. Sin boletín autonómico asociado en cola (`bocm_count: 0`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.concellodeames.gal | Drupal 7 (`basetheme`). |
| Transparencia urbanismo | https://www.concellodeames.gal/es/transparencia/urbanismo-obras-publicas-e-medioambiente | PDFs/ZIP (PXOM, planes especiales, certificaciones). |
| PXOM (acción de goberno) | https://www.concellodeames.gal/es/transparencia/accion-de-goberno/pxom | Enlace al PXOM + planes POS históricos. |
| Sede electrónica | https://sede.concellodeames.gal/eAdmin/Sede.do | Plataforma eAdmin (SemiColonWeb). |
| Tablón digital | https://sede.concellodeames.gal/eAdmin/Tablon.do?action=verAnuncios | Listado HTML por secciones (`Anuncios`, `Urbanismo`, …). |
| Búsqueda tablón | `POST Tablon.do?action=verAnuncios` (`referenciaBusqueda`) | Misma plantilla que listado completo. |
| Catálogo trámites | https://sede.concellodeames.gal/eAdmin/Registrar.do?action=inicioPortalTramites | Modal por trámite → `infoTramite&tipoReg=N`. |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15002 | API `query_document.php` (clases 14 PG, 13 desarrollo). |
| Visor PBA Xunta | https://mapas.xunta.gal/visores/pba/ | Cartografía autonómica de planeamiento. |

## Expedientes / proyectos

- **Tablón sede:** miles de anuncios generales; la tarjeta **Urbanismo** indica «Actualmente, no existen anuncios en está sección». Búsquedas (`PXOM`, `PLANEAMIENTO`, …) no devuelven anuncios urbanísticos recientes en la sección dedicada.
- **SIOTUGA:** PXOM (3 documentos clase 14, p. ej. PXOM 2002, MP01 Bertamiráns 2024) y **51** instrumentos de desarrollo (sectores S-10…S-20, etc.) vía POST JSON con `token` de sesión.
- **Transparencia Drupal:** enlaces directos a ficheros (`modificacion_puntual_pxom_…zip`, plan especial PB3-02, certificaciones).
- Filas del adapter: metadatos SIOTUGA + documentos transparencia + anuncios del tablón cuando coinciden con `RE_PROYECTO`.

## Licencias

- **No** hay tablón ni dataset de licencias concedidas con fecha/distrito/dirección.
- Catálogo sede (grupo Urbanismo, 19 trámites): licencias de obras, comunicaciones previas, certificado urbanístico, etc. (`tipoReg` 37, 58, 51, …).
- Estrategia adapter: páginas informativas de trámites + anuncios del tablón si mencionan licencia (actualmente escasos).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** SIOTUGA (WMS por concello INE 15002); visor PBA Xunta (`mapas.xunta.gal`); no visor municipal propio enlazado a códigos de expediente del tablón.
- **Estrategia:** inventario normativo desde SIOTUGA; polígonos por anuncio/licencia del tablón no enlazables de forma determinista. El orquestador aplica centroide municipal (`manifest` `centroid`) + jitter en `geocode`.
- **Limitaciones:** tablón solo PDF vía `ValidarDocumento.do`; SIOTUGA requiere cookie + `token` por sesión; transparencia Drupal sin API CKAN estable.

## Limitaciones técnicas

- Codificación sede: UTF-8 con caracteres mal decodificados en títulos antiguos (`latin-1` ocasional en PDFs).
- Sección Urbanismo del tablón vacía — no bloquea ingesta (SIOTUGA + transparencia).
- `sync_supabase`: requiere `SUPABASE_DB_URL` en entorno CI/agente.
