# Pulpí — investigación portal ayuntamiento

Municipio: **Pulpí** (`pulpi`) — Almería, Andalucía. INE **04075**. Boletín: BOJA (`boja`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web / sede | https://www.pulpi.es |
| Tablón de anuncios (entidad) | https://www.pulpi.es/Servicios/cmsdipro/index.nsf/tablon_view_entidad.xsp?p=Pulpi |
| PGOU (documento + PDFs) | https://www.pulpi.es/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Pulpi&documentId=6F1FD9086E6B4226C12582880033ECE5 |
| Categoría PGOU | https://www.pulpi.es/Servicios/cmsdipro/index.nsf/tablon_view_entidad_rol_categoria123.xsp?cat1=Normas&cat2=Planeamiento+Urban%C3%ADstico&cat3=PGOU+PULPI&p=Pulpi |
| Guía trámites | https://www.pulpi.es/Servicios/Organizacion/servicios.nsf/serviciosygrupo.xsp?entidad=Ayuntamiento+de+Pulpi |
| Licencia obra mayor | https://www.pulpi.es/Servicios/cmsdipro/index.nsf/servicios.xsp?documentId=68D12EEAF6BC79DAC1258332002A30CD&p=SedePulpi |
| Calificación ambiental | https://www.pulpi.es/Servicios/cmsdipro/index.nsf/servicios.xsp?documentId=6362A33C754472D5C1258332002A32D8&p=Pulpi |
| Oficina virtual (DipAlmería) | https://ov.dipalme.org/TiProceeding/ciudadano?entrada=ciudadano&idEntidad=4075 |
| Visor GIS Diputación | https://app.dipalme.org/visor-gis/ |
| SITUADIFusión (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |

## CMS y listado de expedientes

- **Plataforma:** IBM Domino / XSP **cmsdipro** (plantilla Diputación de Almería), igual que otros ayuntamientos de la provincia.
- **Tablón:** HTML estático en `tablon_view_entidad.xsp` — tabla con `documentId` por fila; detalle en `tablon.xsp?documentId=…` con adjuntos PDF en `archivadoanexos.nsf`.
- **Planeamiento:** PGOU aprobado definitivamente (2018) con ~19 PDFs (normativa, planos clasificación/calificación). Anuncios recientes en tablón: estudios de detalle (sector AG-1, parcela RP-9), información pública, ordenanzas.
- **Licencias:** No hay listado público de concesiones. Trámites informativos en guía de servicios + presentación telemática vía **Oficina Virtual DipAlmería** (certificado / Cl@ve).

## Licencias

- Sin tablón histórico de licencias otorgadas.
- Páginas de trámite: licencia obra mayor, calificación ambiental, oficina virtual.
- El adapter devuelve filas informativas de trámites + cualquier anuncio de tablón que mencione licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Diputación Almería: `https://app.dipalme.org/geoserver/urbanismo/ows` — capa `urbanismo:v_siu_ambitos_o_sectores`, filtro `cod_ine='04075'` (65 features, 64 con nombre de sector).
  - Visor provincial: https://app.dipalme.org/visor-gis/ (SIU + planeamiento ADPDSU).
  - SITUADIFusión Junta de Andalucía (consulta regional, sin API REST pública).
- **Estrategia:** Tras scrape del tablón/PGOU, cruzar título con códigos de sector WFS (`S AG 1`, `S RTU 12`, `UE PUL 1`, …) y rellenar `geom_geojson` desde GeoJSON WGS84 del WFS.
- **Limitaciones:**
  - WFS solo cubre ámbitos/sectores del planeamiento general (SIU), no parcelas ni expedientes puntuales.
  - `geodapulpi.es` es web turística de la Geoda (mina), no visor urbanístico.
  - Tablón sin paginación accesible por GET (solo 30 anuncios recientes visibles).
  - Licencias sin georreferencia pública.
