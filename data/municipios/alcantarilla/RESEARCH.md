# Alcantarilla — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.alcantarilla.es | WordPress (LiteSpeed); área Urbanismo y PGOU/PGMO |
| PGOU / PGMO | https://www.alcantarilla.es/areas/desarrollo-urbano/plan-de-ordenacion-urbana-de-alcantarilla/ | Normas, modificaciones puntuales PGOU 1983, documentación PGMO en trámite (enlaces SharePoint `aytoalc.sharepoint.com`) |
| Urbanismo (área) | https://www.alcantarilla.es/areas/desarrollo-urbano/ | Información de contacto; sin visor propio |
| PIU | https://www.alcantarilla.es/areas/desarrollo-urbano/punto-de-informacion-unico-piu/ | Punto de información (no expedientes online) |
| Sede electrónica | https://alcantarilla.sedipualba.es/ | Plataforma sedipualba (P3000500C) |
| Tablón (home) | https://alcantarilla.sedipualba.es/ | Últimos ~10 anuncios en portada sede |
| Tablón RSS | https://alcantarilla.sedipualba.es/tablondeanuncios/tablon_rss.aspx | ISO-8859-1; mismos anuncios recientes |
| Catálogo URBANISMO | https://alcantarilla.sedipualba.es/catalogoservicios.aspx?area=1197&ambito=1 | Trámites (licencias, DR, comunicación previa, certificados) — solo informativos |
| BORM (PGOU 1983) | https://www.borm.es/services/anuncio/ano/1984/numero/35/pdf?id=709695 | Enlace desde página PGOU |

## Cómo se listan expedientes / proyectos

- **No hay** consulta pública de expedientes urbanísticos en la sede (solo trámite de solicitud de información para interesados).
- **Planeamiento:** documentación PGOU (PDF/SharePoint) y PGMO en tramitación en la página WP; anuncios puntuales en tablón sede (p. ej. dominio público).
- **Adapter:** filas de ámbitos WFS SITMURCIA + enlaces PGOU/PGMO + tablón sede filtrado por keywords urbanísticas.

## Licencias

- Sin registro público de licencias concedidas.
- Trámites sedipualba: licencia urbanística, declaraciones responsables, comunicación previa, ocupación vía pública, etc.
- El adapter devuelve páginas informativas de trámites (patrón Pozuelo) + edictos del tablón si aplican.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS INSPIRE planeamiento CARM: `https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs`
  - Capa: `SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo`
  - Filtro: `Municipio='Alcantarilla'`
  - Campos: `Ambito`, `Clasificacion`, `Area_m2`, `Enlace_ficha`
  - Visor regional: https://sitmurcia.carm.es/planeamiento-urbanistico (actualización IDERM ~nov 2006 para Alcantarilla)
- **Estrategia:** descarga WFS GeoJSON EPSG:4326; una fila por ámbito; join por código UA-/sector en título cuando coincide.
- **Limitaciones:** datos regionales informativos (no sustituyen planos oficiales); tablón sin geometría; SharePoint no georreferenciado; sin visor municipal ArcGIS.

## Limitaciones generales

- Tablón sede: solo anuncios recientes en portada/RSS (sin paginación accesible en `default.aspx` desde el agente).
- PGMO/PGOU mayoritariamente en SharePoint (requiere navegador; URLs estables en HTML WP).
- Sin boletín municipal propio en cola (`bocm_count: 0`).
