# Humes de Madrid — investigación portal ayuntamiento

**Slug cola:** `humes-de-madrid`  
**BOCM regional (referencia):** 1 aviso (probable alias de parseo)  
**Fecha investigación:** 2026-09-19

## Conclusión principal

**«Humes de Madrid» no figura como municipio independiente** en el INE ni en el catálogo territorial de la Comunidad de Madrid (179 municipios en dataset Altitud CM). Es casi seguro un **alias erróneo del parseo BOCM** de **Humanes de Madrid** (INE 28073), municipio ya onboarded en este repositorio como `humanes-de-madrid` (PR #42).

| Evidencia | Resultado |
|-----------|-----------|
| INE municipios Madrid (28070–28073) | Horcajuelo → Hoyo → **Humanes** (no existe «Humes») |
| Datos CM Altitud municipios | 179 entradas; entre Horcajuelo (0719) y Hoyo (0724) no hay «Humes» |
| Wikipedia / Wikidata | No hay artículo «Humes de Madrid» |
| SITCM WFS `VPLA_V_AMBITO` / `ORDENANZA_REF_23` | 0 polígonos para `DS_MUNICIPIO ILIKE '%HUMES%'` |
| Cola `humanes-de-madrid` | `status: done`, PR #42 |

## URLs probadas

| Recurso | URL | Estado |
|---------|-----|--------|
| Web municipal | `https://www.humesdemadrid.es`, `*.madrid`, variantes `ayto*` | **DNS inexistente** |
| Sede espublico (sin guion) | `https://humesdemadrid.sedelectronica.es` | **No operativa** — «Sede Electrónica Indeterminada» |
| Sede espublico (con guion) | `https://humes-de-madrid.sedelectronica.es` | **No operativa** — mismo mensaje |
| Municipio canónico | `https://humanes.sedelectronica.es` | Operativa — ver `humanes-de-madrid` |
| Web canónica | `https://ayto-humanesdemadrid.es` | WordPress (captcha en CI) |

La página «Sede Electrónica Indeterminada» de espublico gestiona indica que el subdominio **no está vinculado** a ningún ayuntamiento (plantilla genérica de selección de sede).

## Proyectos / expedientes

- No hay portal scrapeable propio de «Humes de Madrid».
- El único aviso BOCM en cola (`bocm_count: 1`) debe atribuirse al municipio **Humanes de Madrid** (`humanes-de-madrid`).
- Adapter mínimo: fila estática de referencia al portal canónico + nota de alias.

## Licencias

- Sin listado público bajo el nombre «Humes de Madrid».
- Trámites y tablón en `humanes.sedelectronica.es` (adapter `humanes_de_madrid.py`).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Ninguna capa SITCM ni visor municipal para «Humes de Madrid»; el municipio INE no existe con ese nombre.
- **Estrategia:** No aplica; geocode usará centroide de Humanes de Madrid (config en manifest) + jitter.
- **Limitaciones:** Entrada de cola espuria; sin geometría ni portal propio.

## Recomendación

1. Marcar cola `humes-de-madrid` como **failed** / revisión humana.
2. Reasignar el aviso BOCM parseado a `humanes-de-madrid` en futuras pasadas del parser.
3. No duplicar scraping: usar adapter existente `HumanesDeMadridAyuntamientoAdapter`.
