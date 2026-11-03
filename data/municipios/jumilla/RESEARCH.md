# Investigación portal — Jumilla (Murcia)

**Municipio:** Jumilla (`jumilla`) — Región de Murcia. INE **30032**. Sin boletín BOCM asociado en cola.

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://jumilla.org |
| Sede electrónica (Sedipualba) | https://jumilla.sedipualba.es |
| Tablón de anuncios | https://jumilla.sedipualba.es/tablondeanuncios/ |
| Tablón RSS | https://jumilla.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo trámites Urbanismo (área 1153) | https://jumilla.sedipualba.es/catalogoservicios.aspx?ambito=&area=1153 |
| PGOU (documentación) | https://jumilla.org/ayuntamiento/PGOUJUMILLA.asp |
| Descargas PGOU (PDF) | http://datos.jumilla.org/descargas/ (memoria, normativa, planos serie A–F) |
| Perfil contratante | https://sede.jumilla.org/portal/contratante |

## Listado de expedientes / planeamiento

- **Tablón:** ASP.NET Sedipualba; listado HTML + RSS (~20 ítems recientes). Anuncios urbanísticos puntuales (p. ej. PEPCHA id=29767, información pública obras).
- **PGOU:** página estática con enlaces a PDFs en `datos.jumilla.org` (memoria, normativa, planos).
- **Trámites:** catálogo sede con licencias de segregación, certificados urbanísticos, declaraciones responsables — **sin listado público de licencias concedidas** (solo fichas informativas de trámite).
- No hay visor municipal propio ni API de expedientes urbanísticos enlazable por código.

## Licencias de obra

- Publicación principal vía **tablón** cuando el ayuntamiento edicta resoluciones; no hay dataset ni listado sistemático de licencias.
- Trámites electrónicos documentados en sede (DR, certificados, segregaciones).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS CARM: `https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs`
  - Capa: `SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo`
  - Filtro: `Municipio='Jumilla'` (~362 polígonos; campo `Ambito`, p. ej. `SGH.`)
  - Visor regional: https://sitmurcia.carm.es/planeamiento-urbanistico
- **Estrategia:** descarga WFS GeoJSON EPSG:4326; filas de ámbito PGOU como proyectos con `geom_geojson`; matching por texto en títulos del tablón cuando cite ámbito/código.
- **Limitaciones:** geometría es clasificación de suelo por ámbito PGOU (IDERM), no delimitación de expediente concreto; tablón/PDF sin georreferencia directa; sede no expone coords por licencia.

## Limitaciones generales

- RSS con ventana corta; anuncios antiguos requieren HTML del tablón.
- `jumilla.org/ayuntamiento/` devuelve 403 en algunos paths de directorio; páginas `.asp` concretas accesibles.
- Sin boletín regional en pipeline (`bocm_count: 0`).
