# Alhama de Murcia — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://ayuntamiento.alhamademurcia.es |
| Urbanismo (área) | https://ayuntamiento.alhamademurcia.es/areas/area.asp?id=1 |
| Planeamientos de desarrollo | https://ayuntamiento.alhamademurcia.es/planeamientos-desarrollo.asp |
| Documentos en tramitación | https://ayuntamiento.alhamademurcia.es/documentos-tramitacion.asp |
| Modificaciones PGMO aprobadas | https://ayuntamiento.alhamademurcia.es/modificaciones-aprobadas-definitivamente.asp |
| Tablón de anuncios (web) | https://ayuntamiento.alhamademurcia.es/tablon.asp (~46 páginas, avisos + PDFs) |
| Datos abiertos / PGMO PDFs | https://datos.alhamademurcia.es |
| Sede electrónica (espublico) | https://alhamademurcia.sedelectronica.es (portal «indeterminado», sin tablón operativo) |
| Subsede tributaria | https://subsedeelectronicagestiontributaria.alhamademurcia.es |

## Expedientes / planeamiento

- CMS propio **ASP clásico** (Bootstrap + páginas `.asp` por actuación: planes parciales, estudios de detalle, UAs, modificaciones PGMO).
- Listado maestro en `planeamientos-desarrollo.asp` y enlaces desde el área de Urbanismo.
- **Documentos en tramitación**: HTML con enlaces a PDFs en `datos.alhamademurcia.es` (avances de modificaciones PGMO n.º 6–11, BORM, EAE, edictos de información pública).
- **Modificaciones aprobadas**: PDFs del documento digital de modificaciones N1–N5 del PGMO.
- No hay API JSON ni visor municipal de expedientes abiertos; la información es **HTML + PDF estático**.

## Licencias de obra

- **Tablón web** (`tablon.asp`): avisos (`avisot.asp?id=`) y PDFs en `datos.alhamademurcia.es`; mezcla urbanismo, licencias de actividad/obra y otros edictos (filtrado por palabras clave).
- Sede espublico (`alhamademurcia.sedelectronica.es`) no expone tablón operativo; la publicación oficial está en la web municipal.
- Página informativa adicional: `licencia-actividad-272021.asp` (Ley 27/2021).
- La política de entidades (`reviewed_records`) descarta convocatorias sin evidencia de concesión; muchas licencias del tablón son avisos de trámite.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS CARM / SITMURCIA `SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo` filtrado `Municipio='Alhama de Murcia'` (~436 polígonos). Campos: `Ambito`, `Clasificacion`, `Area_m2`, `Enlace_ficha`.
- **Estrategia:** Tras extraer metadatos del título/texto (códigos SU, UA, SGEL, NUPP, etc.), cruzar con índice WFS y rellenar `geom_geojson` cuando el código coincide.
- **Limitaciones:** Los PDFs y páginas ASP no enlazan objectId GIS; muchos documentos son modificaciones globales del PGMO sin código de ámbito en el título → geometría solo en filas con código reconocible. No hay visor ArcGIS municipal propio.

## Otras limitaciones

- `transparencia.alhamademurcia.es` no responde (HTTPS caído); decretos en HTTP devuelve 404.
- Sede electrónica genérica sin selección de municipio.
- Paginación no aplicable (conjunto finito de páginas semilla + PDFs).
