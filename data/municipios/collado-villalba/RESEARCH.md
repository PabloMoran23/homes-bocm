# Collado Villalba — investigación portal ayuntamiento

## Resumen

Web corporativa en **Liferay** (`https://www.colladovillalba.es`) y **sede electrónica propia**
(`https://sedeelectronica.ayto-colladovillalba.org`, plataforma Java/MDB con tablón electrónico
vía API JSON).

Las fuentes scrapeables principales son el **tablón electrónico** (expedientes publicados) y las
páginas de **urbanismo/planeamiento** con PDFs en `/documents/`.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Urbanismo (portal) | `/urbanismo` | HTML Liferay | Enlaces a sede, tablón, visor usos |
| Proyectos / planes | `/proyectos`, `/pgou`, `/modificaciones-pgou` | HTML + PDF Liferay | Planes parciales, estudios, convenios |
| Tablón virtual | `/portal/noEstatica.do?opc_id=268` | HTML + JS | UI del tablón electrónico |
| API tablón | POST `/sede/tablonElectronico.do` | JSON | `listaExpedientes`, `listaDocumentos`, `listaSubsecciones` |
| Detalle expediente | POST `opcion=verDetalleExpediente` | JSON | Documentos firmados del expediente |
| Catálogo trámites urbanismo | `/portal/noEstatica.do?opc_id=119` | HTML | Fichas informativas licencias/DR |
| Consulta usos | `/consulta-usos-urbanísticos` | HTML | Enlaces a visores ArcGIS |
| SITCM regional | `idem.madrid.org/.../visor.htm` | Visor externo | Cartografía CCAA (no expedientes locales) |

## Estructura tablón electrónico

POST `tablonElectronico.do` con `opcion=consultar`, `opc_id=268`, `ent_id=1`, `subseccion`:

- `TABLONVIRTUAL` → raíz
- `AYTO` → Ayuntamiento
- `AYTO.URB` → **Urbanismo** (7 expedientes, jun 2026): obras con proyecto, planeamiento, reparcelación, IEE
- `AYTO.EDICTOS` → edictos de planeamiento
- `AYTO.ANUN` → anuncios generales (filtrar por keywords urbanismo)

Campos expediente: `idExp`, `anno`, `codigo`, `tipoDes`, `nombre`, `fechaPublicacion`,
`fechaCreacion`, `expedienteCodificado`.

Documentos: `docNom`, `docUrl` (verificación), `docId`, `codVerif`.

Codificación respuesta: **ISO-8859-1**.

## Licencias

No hay listado tabular de concesiones con coordenadas. Fuentes:

- Expedientes tablón tipo «Obras con proyecto» (`AYTO.URB`)
- **Fichas informativas** del catálogo urbanismo (opc_id=119): licencias 314–327, DR 308, cédulas 301–302

## Proyectos / expedientes

- Tablón `AYTO.URB` + `AYTO.EDICTOS` (expedientes con documentos)
- PDFs en `/proyectos` (planes parciales sector 1.x, estudios de detalle, convenios)
- PDFs en `/pgou` y `/modificaciones-pgou`

Ejemplos (jun 2026):

- `2024/18205` — reparcelación polígono PO G-10.1 Cañuelo
- `2025/19183` — corrección Plan Especial Casco Antiguo
- Plan Parcial Sector 1.4 La Huerta (PDF en `/proyectos`)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS Online `urbanismocv.maps.arcgis.com` — webapps:
    - Consulta tramitación electrónica (`4f12063672994617b1c32a8e8f15f911`)
    - Consulta referencia catastral locales (`617b08eaaf834163afb7beb6356e8bff`)
  - FeatureServer parcelas/locales: `Locales_CV_v2_ZonasUrbanisticas/FeatureServer/22`
  - Zonificación: `Zonas_Urbanisticas_Tabla_v4/FeatureServer/32`
  - Edificios catastro: `Building/FeatureServer/0`
- **Estrategia:** query ArcGIS por `nombre_via` / referencia parcela extraída del título del expediente
  (p. ej. «CALLE JUNTERA», «P-29»). Sin campo `expediente` en capas GIS.
- **Limitaciones:** visor muestra zonas y parcelas catastrales, no polígonos por expediente;
  enlace expediente↔geometría requiere heurística por dirección/ref. catastral; muchos expedientes
  son normativos (ordenanzas, IEE) sin ámbito espacial.

## Limitaciones

- Tablón histórico profundo requiere navegar subsecciones (`obtenerSubsecciones` en JS)
- Documentos del tablón vía verificación (`verificarDocumentos.do`), no PDF directo
- Catálogo trámites mezcla urbanismo con otras áreas; filtro por keywords
- Sin dataset abierto de licencias concedidas con coords

## Referencia adapters

- Tablón sede JSON: patrón similar a `villanueva_de_la_canada.py` (STA/tablon)
- Liferay documentos: `pinto.py`, `villaviciosa_de_odon.py`
- ArcGIS query: `sector_geometry/madrid_ayto_sync.py` (`returnGeometry=true`, `outSR=4326`, `f=geojson`)
