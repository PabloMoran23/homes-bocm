# Mérida — investigación portal ayuntamiento

## Resumen

- **Web corporativa:** https://merida.es (WordPress, tema mimotic)
- **Sede electrónica:** https://sede.merida.es (plataforma STA, `ent_id=2`)
- **Provincia / CCAA:** Badajoz, Extremadura

## Fuentes de proyectos / planeamiento

### Planeamiento PGOU / PGM (web)

- **PGOU vigente y documentación:** https://merida.es/servicios-municipales/urbanismo/planeamiento-pgou/
  - PDFs en `https://descargas.merida.es/urbanismo/` (normas, planos, catálogos, programas de actuación).
  - Enlaces al DOE de Extremadura (`doe.gobex.es`, `doe.juntaex.es`) con aprobaciones históricas.
  - Acuerdos recientes en `descargas.merida.es/junta-gobierno/` y `descargas.merida.es/plenos/`.
  - Carpeta `descargas.merida.es/urbanismo/planeamiento/` (p. ej. acceso norte Proserpina).
- **Nuevo PGM en tramitación:** https://merida.es/servicios-municipales/urbanismo/nuevo-pgm/
  - PDF aprobación inicial: `2025-aprobacion-inicial-pgou-merida.pdf`.
- **Plan protección casco histórico:** https://merida.es/servicios-municipales/urbanismo/plan-proteccion-casco-historico/

**Formato:** HTML estático con enlaces directos a PDF; sin API JSON.

### Tablón electrónico sede

- **Página:** https://sede.merida.es/portal/noEstatica.do?opc_id=268&ent_id=2&idioma=1
- **API AJAX:** `POST /sede/tablonElectronico.do` (`opcion=consultar`, `subseccion=TABLONVIRTUAL`).
- **Estado:** en pruebas desde el entorno cloud el endpoint responde `error: true` o HTTP 500; no hay `tablonVirtual.do` con subsección `ANU_ADMON` como en Badajoz.
- **Adapter:** no depende del tablón; proyectos desde PDFs corporativos.

## Licencias de obra

- **Catálogo sede:** https://sede.merida.es/sede/catalogoTramites.do?opcion=detalle&idApl=2&ent_id=2&idioma=1
  - Trámites: licencia obra mayor, comunicación previa obra menor, parcelación, primera utilización, licencias de actividad, certificados de urbanismo, vados, etc. (solo inicio de trámite, no listado de concedidas).
- **Modelos / información:** https://merida.es/servicios-municipales/urbanismo/tramites/ (`descargas.merida.es/urbanismo/modelos/`).
- **Estrategia:** filas informativas por trámite del catálogo + página de modelos; sin dataset de licencias publicadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Página “Geoportal Mérida” (https://merida.es/servicios-municipales/urbanismo/geoportal-merida/): proyecto en diseño (consulta ciudadana 2026); aún no hay visor ArcGIS/WFS público enlazado a expedientes.
  - PGOU: planos y catálogos solo en PDF (`descargas.merida.es/urbanismo/pgou-planos-*.pdf`).
- **Estrategia:** sin query GIS por expediente; el orquestador usará centroide municipal + jitter (`centroid` en manifest).
- **Limitaciones:** delimitación de ámbito solo en planos PDF; sin `geom_geojson` en adapter.

## Limitaciones técnicas

- Codificación sede: ISO-8859-1 en HTML.
- Tablón electrónico JSON no fiable para scrape automatizado (error servidor).
- `request_delay_s` ≥ 0.35 s recomendado.
- SSL válido en web y sede.

## Referencia de implementación

- PDFs corporativos + sede catálogo: patrón similar a `municipio/adapters/badajoz.py` (sin tablón ANU_ADMON) y filas informativas de licencias como Pozuelo.
