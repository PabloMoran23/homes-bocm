# Hellín — investigación portal ayuntamiento

Municipio: **Hellín** (`hellin`), provincia Albacete, Castilla-La Mancha. INE **02037** (código entidad Diputación Albacete en sede).

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|-------|
| Web oficial | https://www.hellin.es | Joomla; **certificado SSL no verificable** (caducado/emisor incompleto) |
| Sede electrónica | https://hellin.sedipualba.es | ASP.NET Sedipualba (Dip. Albacete) |
| Tablón anuncios | https://hellin.sedipualba.es/tablondeanuncios/default.aspx | HTML + filtros área/mes |
| Tablón RSS | https://hellin.sedipualba.es/tablondeanuncios/tablon_rss.aspx | ISO-8859-1, ~20 ítems recientes |
| Catálogo trámites | https://hellin.sedipualba.es/catalogoservicios.aspx | Área «Urbanismo y Actividades» (p. ej. `area=776&ambito=1`) |
| eAdmin legacy (web) | https://eadmin.dipualba.es/tablondeanuncios/default.aspx?entidad=02037 | Enlace desde web; sirve contenido sede Hellín |
| Sede Dip. Albacete | https://sede.dipualba.es/?entidad=02037 | Portal provincial |
| PET / PSTD (transparencia) | https://www.hellin.es/index.php/2013-11-14-00-43-08/pet | Plan Estratégico Territorial |
| | https://www.hellin.es/index.php/2013-11-14-00-43-08/pstd | Plan Sostenibilidad Turística Destino |
| Trámites (web) | https://www.hellin.es/index.php/2013-11-14-00-45-19/tramites-electronicos | Enlaces a sede |

## Cómo se listan expedientes / proyectos

- **Tablón Sedipualba:** RSS + HTML tabular. Edictos de información pública (p. ej. ocupación terrenos MUP, ordenanzas), convocatorias plenos, etc. PDFs vía `documento.aspx?id=…`.
- **Catálogo trámites:** fichas informativas (`tramite.aspx?idtramite=…`) para licencias (obra menor DR, vado, conexión agua) — **no** listado de expedientes abiertos ni concesiones históricas.
- **Web municipal:** páginas estáticas PET/PSTD; sin visor urbanístico ni listado de planeamiento por expediente.

Patrón de scrape: RSS tablón + regex urbanismo + fila PGOU desde ArcGIS CLM + semillas PET/PSTD.

## Licencias de obra

- No hay registro público de licencias concedidas (solo trámites informativos y edictos puntuales en tablón si el ayuntamiento publica resoluciones).
- Adapter devuelve trámites URB/licencia del catálogo + fila referencia al tablón (paridad mínima).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS CLM `Planeamiento_Municipal/MapServer/0` — query `COD_INE='02037'` → polígono **Plan de Ordenación Municipal** (GeoJSON WGS84).
  - No visor municipal ArcGIS/WFS enlazado a expedientes.
  - Tablón/PDF sin georreferencia explícita (referencias textuales MUP/parcela sin API).
- **Estrategia:** fila proyecto `PGOU/POM — Hellín (CLM)` con `geom_geojson` del servicio regional; edictos tablón sin geometría (centroide municipio + jitter en orquestador).
- **Limitaciones:** SSL web ayuntamiento; sin capa parcelaria municipal; CLM no distingue expedientes individuales.

## Limitaciones generales

- Certificado SSL `www.hellin.es` — usar `insecure_ssl: true` en manifest.
- Tablón mezcla anuncios no urbanísticos (personal, subvenciones); filtrado por regex.
- Presentación trámites requiere certificado digital; sin API pública de expedientes.
