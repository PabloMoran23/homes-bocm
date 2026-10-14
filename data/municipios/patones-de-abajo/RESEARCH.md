# Patones de Abajo — investigación portal ayuntamiento

**Slug cola:** `patones-de-abajo`  
**Nombre BOCM:** Patones de Abajo (1 aviso)  
**Fecha:** 2026-09-28

## Hallazgo principal

**Patones de Abajo** no es un municipio independiente: es la **entidad local / núcleo de población** donde está la sede del **Ayuntamiento de Patones** (INE 28107, código postal 28189). El municipio único incluye también Patones de Arriba. La cola BOCM usa el nombre de la localidad en un aviso; el portal y los datos públicos son los del municipio Patones (adapter `patones`, mergeado 2026-08-01).

| Evidencia | Detalle |
|-----------|---------|
| INE / Wikipedia | Un solo municipio «Patones»; núcleos Patones de Abajo y Patones de Arriba |
| Sede ayuntamiento | Plaza de la Constitución, Patones de Abajo — portal `patones.net/site/ayto` |
| Cola hermana | `patones` — 17 avisos BOCM, mismo portal |

**Decisión:** reutilizar fuentes del adapter `patones.py` y etiquetar filas con `municipio: Patones de Abajo` + prefijo id `patones-de-abajo-*` para cruce BOCM.

## URLs base y semillas (Ayuntamiento de Patones)

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress) | https://patones.net/site/ayto/ | Portal activo (`www.patones.es` inaccesible) |
| Urbanismo / arquitecto municipal | https://patones.net/site/ayto/arquitecto-municipal/ | PAMIF, PAMINUN, planes especiales (PDFs) |
| Normas subsidiarias | https://patones.net/site/ayto/normas-subsidiarias/ | ~52 PDFs (UE en nombres de archivo) |
| Bandos / boletín | https://patones.net/site/ayto/bandos/ | Bandos municipales |
| Sede (espublico) | https://patones.sedelectronica.es/board | Tablón de anuncios (HTML tabla) |
| Transparencia | https://patones.sedelectronica.es/transparency | URBANISMO (Wicket, no scrapeable) |

Documentación ampliada: `data/municipios/patones/RESEARCH.md`.

## Expedientes y licencias

- **Proyectos:** WordPress (NNSS, planes, bandos), PDFs semilla, tablón sede filtrado, ámbitos WFS SITCM (mismo patrón `patones.py`).
- **Licencias:** sin registro público de concesiones; trámites informativos + tablón filtrado.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS IDEM/SITCM `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='PATONES'` (15 UE del término municipal, incluye vega de Patones de Abajo).
- **Estrategia:** query WFS por código UE en título; `geom_geojson` WGS84 + `geometry_source: portal_wfs`.
- **Limitaciones:** sin visor municipal por expediente; geometría solo para ámbitos UE identificables; datos duplicados respecto a slug `patones` salvo etiqueta e ids.

## Limitaciones

- Slug cola = localidad, no municipio INE distinto.
- `/dossier` sede con redirect loop.
- Transparencia no scrapeable.

## Referencias de implementación

- Adapter base: `municipio/adapters/patones.py`
- Wrapper slug: `municipio/adapters/patones_de_abajo.py`
