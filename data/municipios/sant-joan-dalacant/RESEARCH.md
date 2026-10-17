# Sant Joan d'Alacant — alias `sant-joan-dalacant`

## Relación con pipeline canónico

| Campo | Valor |
|-------|-------|
| Slug cola (esta entrada) | `sant-joan-dalacant` |
| Slug canónico / adapter | `sant-joan-d-alacant` |
| INE | 03119 (Alicante) |
| Boletín | DOGV (`dogv`) |

La investigación detallada del portal, fuentes y limitaciones está en
[`../sant-joan-d-alacant/RESEARCH.md`](../sant-joan-d-alacant/RESEARCH.md).

Este slug aparece en `ccaa_history_parsed_incremental.csv` con otra normalización
del nombre; el municipio INE es el mismo y comparte portal y adapter.

## URLs (resumen)

| Fuente | URL |
|--------|-----|
| Web | https://www.santjoandalacant.es |
| Urbanismo | https://www.santjoandalacant.es/area-urbanismo/ |
| Sede / tablón | https://santjoandalacant.sedelectronica.es/board |
| Trámites | https://santjoandalacant.sedelectronica.es/dossier |

## Geometría / visor

- **geometry_status:** `unavailable` en el adapter actual (sin enlace expediente↔polígono).
- **ICV WFS** `InventarioSuSuz` con `cod_ine_mun=03119` devuelve miles de polígonos SUZ/UA
  (`terramapas.icv.gva.es/0702_Planeamiento`), pero no están enlazados a filas del tablón ni
  a PDFs del WordPress; enriquecimiento futuro vía capa ICV (patrón Vinaròs/Alfafar).
- Orquestador: centroide municipio + jitter.

## Adapter

`municipio.adapters.sant_joan_d_alacant:SantJoanDAlacantAyuntamientoAdapter` (compartido con slug canónico).
