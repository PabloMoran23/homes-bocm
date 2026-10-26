# Marratxí — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|--------|
| Slug | `marratxi` |
| Web principal | https://www.marratxi.es |
| CMS | WordPress (Avada) + WPML (ca/es) |
| Sede electrónica | https://marratxi.sedelectronica.es → **Indeterminada** (sin URL de gestión) |
| Portal ayuda | https://info.marratxi.es/urbanisme/ |
| CCAA | Illes Balears (sin filas BOCM en cola) |

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Urbanisme (área) | https://www.marratxi.es/urbanisme/ |
| Normativa municipal (urbanismo, PDFs llicències) | https://www.marratxi.es/normativa-municipal/ |
| IEE / edificios | https://www.marratxi.es/iee/ |
| Tràmits (índice) | https://www.marratxi.es/tramits/ |
| FAQ urbanisme | https://info.marratxi.es/urbanisme/ |
| Normes subsidiàries (BOIB) | http://boib.caib.es/pdf/1999154/mp16748.pdf |
| Transparencia | https://transparencia.marratxi.es/ |

## Cómo se listan expedientes / proyectos

- **No hay** tablón electrónico ni visor municipal de expedientes enlazado.
- **Información pública / planeamiento:** noticias en `www.marratxi.es` (WP REST API) con títulos tipo «Exposició pública del projecte…», obras municipales (skatepark, via verda, etc.).
- **Normativa y modelos:** página `normativa-municipal` con anclas HTML; PDFs de cédula urbanística, edictos de aprobación y formularios de llicència (obra major/menor, final d'obra).
- **Enlace roto:** `ajuntament.marratxi.es/normativa-municipal/` (404); la copia válida está en `www.marratxi.es/normativa-municipal/`.

## Licencias de obra

- **No se publican** concesiones nominativas (sin sede operativa).
- Modelos y tasas en normativa municipal (`OBRA-MENOR.pdf`, `OBRA-MAJOR.pdf`, `FINAL-DOBRA.pdf`).
- Noticia informativa (2026-07-14) sobre tramitación de llicències via ECU.
- FAQ infracciones / IAE en portal d'ajuda.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** IDE IDELMA código **M043** (`M043_Annex1_*`, `M043_Municipal`, redes) — sin workspace `M043_URBANISME` ni capa `exp_absis` (contrasta con Pollença M042).
- **Estrategia:** no hay join expediente↔polígono; el orquestador usará `centroid` del manifest + jitter.
- **Limitaciones:** sede espublico no resuelta; sin WFS de expedientes; PGOU solo como capas estáticas IDELMA no enlazadas a anuncios web.

## Adapter

- `municipio.adapters.marratxi:MarratxiAyuntamientoAdapter`
- Fuentes: normativa municipal (PDFs), semillas web, noticias WP filtradas, trámites informativos.

## Limitaciones

- Sin listado público de expedientes urbanísticos ni licencias concedidas.
- WP search genérico muy ruidoso; el adapter filtra por título/regex acotados.
- `queue claim` re-serializa `queue.yaml`; al cerrar PR parchear **solo** el bloque `marratxi`.
