# Mieres — investigación portal ayuntamiento (slug cola `mieres-33037`)

Municipio: **Mieres** (`mieres-33037` → canónico `mieres`) — Asturias, INE **33037**  
Boletín: BOPA (`boletin_source_id: bopa`; entrada duplicada en cola sin contador)

> Implementación compartida con `data/municipios/mieres/` (PR #1049). Este slug desambigua homónimos (p. ej. Mieres/Girona INE 17105).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.mieres.es | WordPress — urbanismo, PGOU, trámites |
| Urbanismo | https://www.mieres.es/areas-municipales/urbanismo/ | Índice urbanismo |
| PGOU | https://www.mieres.es/areas-municipales/urbanismo/plan-general-de-ordenacion-urbana-de-mieres/ | Documentación PGOU |
| Trámites online | https://www.mieres.es/ayuntamiento/instancias-enlaces-a-tramites-online/ | MI20-* licencias, DR |
| Sede STA | https://sedeelectronica.ayto-mieres.es | Tablón `PTS2_TABLON`, catálogo trámites |
| Tablón | `.../doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON` | JSON embebido `dataset_PTS2_TABLON` |
| RPGUR | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento regional |
| Listado Mieres | `busquedaConsulta?method=listPublico&idConcejo=37&estado=V` | Instrumentos vigentes (HTML paginado) |

## Cómo se listan expedientes / proyectos

1. **RPGUR:** tabla HTML por `idConcejo=37`; detalle `gestionConsulta?method=retrieve&idInstrumento=N`.
2. **Tablón sede:** array JSON en página STA (~87 anuncios; subset urbanismo).
3. **Web municipal:** crawl WordPress urbanismo/PGOU PDFs.

## Cómo se publican licencias

- Sin listado público de concesiones georreferenciadas.
- Trámites informativos en sede (licencia obra mayor, etc.) y tablón general.
- Adapter: anuncios tablón + páginas trámite (patrón Asturias/Pozuelo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `id_municipio=33037`
  - Enlace: `Id._Inventario_Registro_Urbanístico` ↔ `idInstrumento` RPGUR
- **Estrategia:** precarga WFS; `_attach_geometry` en adapter `mieres.py`.
- **Limitaciones:** solo PGO/PGOU/CAU con polígono (~3); RPGUR/WFS pueden timeout desde cloud; visor HTML sin API REST.

## Limitaciones generales

- RPGUR ISO-8859-1; host legacy `rpgur.asturias.es` no resuelve — usar `www54.asturias.es`.
- Tablón STA carga lenta (~10s).
- Ver investigación extendida en `data/municipios/mieres/RESEARCH.md`.
