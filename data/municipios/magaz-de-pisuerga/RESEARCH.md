# Magaz de Pisuerga — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal | https://magazdepisuerga.es |
| Urbanismo (CPT `ic_urbanismo`) | https://magazdepisuerga.es/urbanismo/ |
| Estudio detalle San Pedro | https://magazdepisuerga.es/urbanismo/parcela-san-pedro-no4-estudio-de-detalle-modificacion-alineaciones/ |
| Modificación PP polígono industrial | https://magazdepisuerga.es/urbanismo/plan-parcial-del-poligono-industrial-de-magaz-de-pisuerga-modificacion-puntual/ |
| Sede electrónica (espublico) | https://magazdepisuerga.sedelectronica.es |
| Tablón de anuncios | https://magazdepisuerga.sedelectronica.es/board |
| PLAU JCyL (archivo) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=34&municipio=098 |
| PLAI JCyL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=34&municipio=098 |
| SiuCyL / visor regional | https://idecyl.jcyl.es/siur/index.html?id=34098 |

## CMS y formato de datos

- **Web:** WordPress + Divi (plugin municipios Diputación de Palencia). CPT `ic_urbanismo` en `/urbanismo/`. REST API deshabilitada (401); scraping HTML del archive y posts individuales. Descargas vía Download Monitor (`/download/`).
- **Sede:** espublico gestiona. Tablón en `/board` (tabla HTML con `preview-document`). Catálogo de trámites en `/dossier/.0` (lento; timeout posible en CI).
- **Proyectos:** 2 entradas WP + 10 documentos PLAU JCyL + capas WFS IDECyL (instrumentos, planes parciales, sectores).
- **Licencias:** no hay listado público de concesiones en tablón; trámite destacado en sede: «Declaración Responsable, Solicitud de Licencia o Comunicación en Materia Urbanística». Solo páginas informativas de trámite.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1), `urbanismo:plau_cyl_planes_parciales` (2), `urbanismo:plau_cyl_sectores` (12)
  - Filtro: `CQL_FILTER=n_mun='Magaz de Pisuerga'`
  - Campos: `n_num_sect` (p. ej. `Sector IV`, `Sector VIII`, `Sector C`), `c_id_sect`, `n_sector`
- **Estrategia:** descarga WFS por municipio; enriquecimiento por código de sector en títulos PLAU/WP/tablon (`Sector VIII`, `PRAU MAGAZ NORTE`, etc.).
- **Limitaciones:** no hay visor municipal propio; geometría a nivel de sector/instrumento PGOU, no por expediente individual. Tablón sin anuncios urbanísticos recientes. PDFs WP sin georreferencia.

## Limitaciones generales

- Tablón sede (~10 filas recientes) sin urbanismo en el periodo actual (solo administrativo/tributario).
- `/municipio/vivienda/urbanismo/` (ruta antigua) devuelve 404; usar `/urbanismo/`.
- INE 34098, provincia Palencia (34), código PlanPublica 098.
- BOCYL: 1 expediente histórico en cola (parque eólico/fotovoltaico); datos portal son planeamiento municipal.
