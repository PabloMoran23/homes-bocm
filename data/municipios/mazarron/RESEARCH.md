# Mazarrón — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (OpenCms) | https://www.mazarron.es | Noticias y sección Infraestructuras y Urbanismo |
| Planes / PGMO | https://www.mazarron.es/es/infraestructuras-y-urbanismo/planes/ | ~67 entradas (información pública, aprobaciones, estudios de detalle, sectores S-03-*) |
| Convenios urbanísticos | https://www.mazarron.es/es/infraestructuras-y-urbanismo/convenios/ | Convenios de gestión/ejecución PGMO |
| Licencias (informativo) | https://www.mazarron.es/es/infraestructuras-y-urbanismo/licencias-urbanisticas/ | Modelos y trámites; sin registro público de concesiones |
| Trámites urbanismo | https://www.mazarron.es/es/ayuntamiento/tramites-y-servicios/urbanismo/ | Enlaces a sede |
| Sede electrónica (STA / T-Systems) | https://sede.mazarron.es | Carpeta pública PTS2 (tablón, catálogo) |
| Tablón edictos | https://sede.mazarron.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all | Dataset embebido `dataset_PTS2_TABLON` (JSON en HTML) |
| Catálogo trámites | https://sede.mazarron.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | `dataset_CATSERV` (p. ej. licencia de obra mayor) |
| Planeamiento regional | https://sitmurcia.carm.es/planeamiento-urbanistico | Visor/fichas SITMURCIA (referencia) |

## Listado de expedientes / proyectos

- **Web planes/convenios:** URLs semánticas bajo `/es/infraestructuras-y-urbanismo/planes/…` y `/convenios/…`; título inferido del slug (sin API).
- **Tablón STA:** array JSON en página del tablón; pocas entradas urbanísticas activas en el momento de la investigación (174 resoluciones abiertas en metadatos del tablón, dataset paginado reducido en HTML).
- **Catálogo STA:** trámites informativos (licencia obra mayor, certificados urbanísticos).

## Licencias

- No hay listado público de licencias concedidas con ubicación.
- Edictos de obra/licencia pueden publicarse en tablón STA (filtro textual).
- Trámites de solicitud vía catálogo sede + página de modelos en web.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS CARM/SITMURCIA: `SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo` con `Municipio='Mazarrón'` (~256 features; campo `Ambito`, p. ej. `S_03-08. Faro.`, `A_05-01/04. Puerto de Mazarrón.`).
  - Visor regional: https://sitmurcia.carm.es/planeamiento-urbanistico
  - Ficha por ámbito (enlace en WFS `Enlace_ficha`): `http://opweb.carm.es/sitmurcia/potgisfichacen.jsp?…`
- **Estrategia:** extraer códigos `S_03-NN`, `A_05-01/NN`, `SGEL-NN` o nombres de sector del título web y cruzar con índice WFS en memoria.
- **Limitaciones:** WFS regional puede estar desfasado respecto al PGMO municipal; tablón STA sin geometría; licencias sin georreferencia; dataset tablón en HTML no expone histórico completo vía JSON.

## Notas técnicas

- INE municipio: **30027**.
- Sede STA usa mismos patrones que otros ayuntamientos T-Systems (`dataset_PTS2_TABLON`, detalle `DETALLE={dboid}`).
- Centroide municipal aproximado: 37.599, -1.314.
