# Náquera — investigación portal ayuntamiento

## Fuentes

| Recurso | URL | Notas |
|---------|-----|-------|
| Web municipal | https://www.naquera.es | Drupal 10 (Generator meta), CA/ES |
| Sede electrónica | https://naquera.sedelectronica.es | espublico gestiona |
| Tablón de anuncios | https://naquera.sedelectronica.es/board/ | HTML tabla `class_name`, preview-document |
| Transparencia | https://naquera.sedelectronica.es/transparency | Enlace desde menú principal |
| Avisos urbanismo | `/va/aviso/...`, `/es/aviso/...` | PGOU / aprobaciones pleno (descubiertos en portada) |
| Planos municipales | `/va/pagina/planols`, `/es/pagina/planos` | Páginas estáticas Drupal |
| Urbanizaciones | `/va/pagina/urbanitzacions-i-associacions` | Información urbanística general |

## Listado de expedientes / proyectos

- **Tablón:** filas con procedimiento (p. ej. «Planeamiento General»), fecha `dd/mm/yyyy`, enlace `/preview-document/{uuid}`.
- **Avisos Drupal:** título en `<h1>`, PDFs enlazados; rutas `/va/aviso/` (no usa `pagina-aviso` como otros Portales).
- **Licencias:** no hay dataset público de concesiones; trámites vía sede (`/dossier`, `/expedientes` con Cl@ve).

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS ICV `InventarioSuSuz`: `https://terramapas.icv.gva.es/0702_Planeamiento` (filtrar `cod_ine_mun=46181` en cliente; CQL no fiable).
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz
- **Estrategia:** paginar WFS (GML3, `srsName=EPSG:4326`), polígonos por sector SU/SUZ; enriquecer avisos/tablón por coincidencia de tokens UE/sector en título.
- **Limitaciones:**
  - ~69 polígonos ICV vs. avisos puntuales sin enlace 1:1 al visor.
  - Tablón mezcla PUAM administrativo (filtrado en adapter).
  - Web municipal a veces lenta (timeouts >30s en listados).

## BOCM / DOGV

- `boletin_source_id`: dogv (1 entrada en cola BOCM).
