# Roquetas de Mar — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.roquetasdemar.es |
| Urbanismo y patrimonio | https://www.roquetasdemar.es/tu-ayuntamiento/areas-municipales/urbanismo-y-patrimonio |
| Ordenación urbanística (PGOU, innovación, PDFs) | https://www.roquetasdemar.es/tu-ayuntamiento/areas-municipales/urbanismo-y-patrimonio/ordenacion-urbanistica |
| PGOU 2009 | https://www.roquetasdemar.es/tu-ayuntamiento/areas-municipales/urbanismo-y-patrimonio/ordenacion-urbanistica/pgou-2009 |
| Sede electrónica (Insuit) | https://sede.aytoroquetas.org/portal/entidades.do?ent_id=1&idioma=1 |
| Tablón virtual | https://sede.aytoroquetas.org/portal/noEstatica.do?opc_id=268&ent_id=1&idioma=1 |
| API tablón (POST JSON) | `https://sede.aytoroquetas.org/sede/tablonElectronico.do` (`opcion=consultar`, `subseccion=TABLONVIRTUAL` → TAB1–TAB4) |
| Transparencia | https://www.roquetasdemar.es/transparencia |

Nota: el host genérico `roquetasdemar.sedelectronica.es` muestra selector de sede; la sede operativa es **sede.aytoroquetas.org**.

## Proyectos / planeamiento

- **Drupal 11**: páginas de ordenación con decenas de PDFs (PGOU 2009, innovación de planeamiento 2024–2026, estudios, BOJA/BOP).
- **Tablón TAB2 (Edictos)**: edictos de aprobación inicial de innovación de planeamiento, consulta pública PGOM/POU, etc.
- **SITUA** (Junta de Andalucía): consulta del planeamiento aprobado / en tramitación (`cid=04079`, INE Roquetas de Mar).
- No hay listado público de expedientes de planeamiento con código enlazable a GIS municipal; el detalle está en PDFs y edictos.

## Licencias de obra

- No hay dataset abierto de concesiones de licencias con coordenadas.
- **TAB3 (Bandos)**: avisos de obras en vía pública (fresado, asfaltado, cortes de calle, redes) — útil como señales de actuación, sin expediente de licencia individual.
- **TAB2**: edictos puntuales; pocas licencias explícitas.
- Trámites de licencia en catálogo de sede (presentación telemática); sin resoluciones masivas publicadas en HTML scrapeable.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor GIS Diputación de Almería: https://app.dipalme.org/visor-gis/
  - WFS GeoServer: `urbanismo:v_siu_ambitos_o_sectores` con `CQL_FILTER=cod_ine='04079'` (110 polígonos de sector / ámbito).
  - SITUA: documentación y mapas del planeamiento regional; sin API REST por expediente municipal enlazable desde el tablón.
- **Estrategia:** tras extraer título de proyecto/edicto, intentar cruce por nombre de sector (`UE-*`, `POP-*`, `Sector N`, fichas PGOU) contra WFS DipAlmería; centroide WGS84 en fila.
- **Limitaciones:** títulos de edictos genéricos sin código de sector → sin polígono; licencias sin georreferencia; visor municipal no expone query por expediente.

## Limitaciones técnicas

- Tablón requiere **sesión** (`JSESSIONID`) tras visitar la página del tablón antes del POST JSON.
- Codificación mixta ISO-8859-1 / UTF-8 en sede Insuit.
- TAB1 del tablón es empleo/oposiciones (excluido del scrape urbanístico).
