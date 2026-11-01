# Olmedo de las Fuentes — investigación portal ayuntamiento

**Slug cola:** `olmedo-de-las-fuentes`  
**Nombre en BOCM parseado:** Olmedo de las Fuentes (1 aviso)  
**Comunidad:** Comunidad de Madrid (`bocm`)

## Hallazgo principal

El municipio oficial del INE es **Olmeda de las Fuentes** (`olmeda-de-las-fuentes`, ya integrado). La entrada `olmedo-de-las-fuentes` es un **error ortográfico** en el CSV de boletines (Olmedo vs Olmeda). No existe ayuntamiento ni dominio distinto.

| Evidencia | Detalle |
|-----------|---------|
| Web oficial | https://olmedadelasfuentes.es — «Ayuntamiento de Olmeda de las Fuentes» |
| Cola hermana | `olmeda-de-las-fuentes` — 6 avisos BOCM, adapter completo |
| INE / código postal | 28515 Olmeda de las Fuentes (Madrid) |

**Decisión:** reutilizar el portal de Olmeda de las Fuentes; filas con `municipio: Olmedo de las Fuentes` e ids `olmedo-de-las-fuentes-*` para cruce con el aviso BOCM.

Documentación detallada de fuentes: `data/municipios/olmeda-de-las-fuentes/RESEARCH.md`.

## URLs base y semillas (portal Olmeda de las Fuentes)

| Recurso | URL |
|---------|-----|
| Web municipal | https://olmedadelasfuentes.es |
| Área urbanismo | https://www.olmedadelasfuentes.es/areas/urbanismo-mantenimiento-e-imagen-urbana |
| PGOU | https://www.olmedadelasfuentes.es/pgou |
| Normativa urbanismo | https://olmedadelasfuentes.es/normativa-de-urbanismo |
| Sede (espublico gestiona) | https://olmedadelasfuentes.sedelectronica.es |
| Tablón | https://olmedadelasfuentes.sedelectronica.es/board |
| Transparencia sede | https://olmedadelasfuentes.sedelectronica.es/transparency |

## Cómo se listan expedientes / licencias

- **Proyectos:** PDFs PGOU/normativa en web; noticias urbanismo; ámbitos SITCM vía WFS; anuncios en tablón/transparencia sede (preview-document).
- **Licencias:** formularios LU/DR en catálogo web; resoluciones en transparencia sede cuando se publican. Sin dataset de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS SITCM `sitcm:VPLA_V_AMBITO`, `DS_MUNICIPIO='OLMEDA DE LAS FUENTES'` (12 ámbitos AA/SUS/AUNI).
- **Estrategia:** misma que `olmeda-de-las-fuentes` — polígonos WFS + match por código en título.
- **Limitaciones:** sin visor municipal; licencias sin polígono parcelario; expedientes sede requieren Cl@ve.
