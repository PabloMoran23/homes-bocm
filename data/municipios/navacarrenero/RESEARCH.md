# Navacarrenero — investigación portal ayuntamiento

**Slug cola:** `navacarrenero`  
**Nombre en BOCM parseado:** Navacarrenero (1 aviso)  
**Fecha:** 2026-09-26

## Hallazgo principal

No existe municipio con este nombre en el INE ni ayuntamiento con dominio propio (`navacarrenero.es` → NXDOMAIN). La entrada de cola procede del CSV de boletines con el campo `municipio` mal escrito; el municipio real es **Navalcarnero** (slug `navalcarnero`, ya integrado en PR #25).

| Evidencia | Detalle |
|-----------|---------|
| INE / ayuntamiento.es | Sin ficha para «Navacarrenero» |
| DNS | `navacarrenero.es`, `ayto-navacarrenero.es` inexistentes |
| Portal operativo | `https://navalcarnero.es` (Navalcarnero, Madrid) |
| Cola hermana | `navalcarnero` — 37 avisos BOCM, adapter completo |

**Decisión:** reutilizar el portal oficial de Navalcarnero y etiquetar filas con `municipio: Navacarrenero` + prefijo de id `navacarrenero-*` para cruce con el aviso BOCM huérfano.

## URLs base y semillas (portal Navalcarnero)

| Fuente | URL | Formato |
|--------|-----|---------|
| Urbanismo + mapa obras | https://navalcarnero.es/navalcarnero/urbanismo/ | WordPress + MapPress (`mapdata`) |
| RSS urbanismo | https://navalcarnero.es/navalcarnero/urbanismo/feed/ | RSS |
| Transparencia urbanismo | https://transparencia.navalcarnero.es/obras-publicas-y-urbanismo/ | WordPress + PDFs |
| Tablón anuncios | https://navalcarnero.es/navalcarnero/tablondeanuncios/feed/ | RSS |
| Trámites licencias | https://navalcarnero.es/navalcarnero/tramites/?category=71 | Formularios descargables |
| Sede | https://sede.navalcarnero.es/ | Trámites (login) |

Documentación ampliada: `data/municipios/navalcarnero/RESEARCH.md`.

## Expedientes y licencias

- **Proyectos:** mapa MapPress, RSS planeamiento, PDFs transparencia, filtro tablón (mismo patrón que adapter `navalcarnero.py`).
- **Licencias:** sin registro público de concesiones; trámites informativos + anuncios tablón filtrados.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** MapPress en página urbanismo (POIs lat/lng); polígono buffer ~30 m vía helper del adapter base; visor IDEM/SITCM regional sin enlace a expediente municipal.
- **Estrategia:** extraer `mapdata.pois` del HTML urbanismo; `geom_geojson` en WGS84 para obras georreferenciadas.
- **Limitaciones:** planes/PGOU solo PDF; sede con login; no ArcGIS municipal.

## Limitaciones

- Slug cola no corresponde a entidad local distinta — revisar limpieza del CSV BOCM.
- Datos duplicados respecto a `navalcarnero` salvo etiqueta `municipio` e ids.

## Referencias de implementación

- Adapter base: `municipio/adapters/navalcarnero.py`
- Wrapper slug: `municipio/adapters/navacarrenero.py`
