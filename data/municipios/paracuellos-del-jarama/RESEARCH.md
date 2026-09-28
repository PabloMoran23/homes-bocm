# Paracuellos del Jarama — investigación portal ayuntamiento

**Municipio:** Paracuellos del Jarama (`paracuellos-del-jarama`, Comunidad de Madrid)  
**Fecha:** 2026-09-28  
**BOCM regional (referencia):** 1 aviso (slug alias en cola)

> **Nota:** `paracuellos-del-jarama` y `paracuellos-de-jarama` son el **mismo municipio** (INE 28121). La investigación detallada del portal está en [`../paracuellos-de-jarama/RESEARCH.md`](../paracuellos-de-jarama/RESEARCH.md).

## Resumen

Misma sede electrónica Insuit (`sede.paracuellosdejarama.es`): tablón JSON, catálogo de trámites urbanismo y enriquecimiento geométrico vía WFS SIT CM `sitcm:VPLA_V_AMBITO`. Web corporativa Drupal bloqueada por Cloudflare en entornos automatizados.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Sede inicio | `https://sede.paracuellosdejarama.es/portal/entidades.do?ent_id=1&idioma=1` | HTML | Tablón, catálogo |
| Tablón API | `POST .../sede/tablonElectronico.do` (`opc_id=268`) | JSON | URB, EDICTO, bandos, … |
| Catálogo trámites | `.../catalogoTramites.do?opcion=detalle&idApl=1` | HTML | Licencias, planeamiento |
| SIT CM WFS | `https://idem.comunidad.madrid/geoserver3/ows` `sitcm:VPLA_V_AMBITO` | GeoJSON | Ámbitos planeamiento |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS SIT CM (`DS_MUNICIPIO='PARACUELLOS DE JARAMA'`); geoportal TecnoGeoWS sin API por expediente.
- **Estrategia:** emparejar título tablón con `DS_NOMB_AMB` / códigos UE-*, AD-*, S-* (mismo adapter que `paracuellos-de-jarama`).
- **Limitaciones:** Drupal corporativo 403 Cloudflare; geometría solo cuando el título coincide con ámbito SIT.

## Licencias

Edictos en tablón cuando se publican; fichas informativas de trámite en catálogo sede (sin histórico de concesiones georreferenciadas).

## Implementación

- Adapter: `municipio.adapters.paracuellos_de_jarama:ParacuellosDeJaramaAyuntamientoAdapter` con `id_prefix: paracuellos-del-jarama`.
- IDs: `paracuellos-del-jarama-{lic|proy}-{sha256[:14]}`.
