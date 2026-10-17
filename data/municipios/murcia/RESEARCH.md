# Murcia — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Formato |
|--------|-----|---------|
| Sede electrónica (tablón) | https://sede.murcia.es/tablon-de-anuncios | Drupal 10, tarjetas HTML + PDF en `/sites/default/files/archivos-anuncios/` |
| Urbanismo (portal Liferay) | https://www.murcia.es/web/urbanismo/inicio | Enlaces a infourb y trámites sede |
| Información urbanística (infourb) | http://urbanismo.murcia.es/infourb/ | ASP.NET; **Últimas publicaciones** con bloques `mitipodiv` (figura, expediente, fecha, enlaces `desarrollo.aspx?sc=` / `plangeneral.aspx?pg=`) |
| Trámites urbanismo | https://sede.murcia.es/ficha-categoria/10001 | Listado procedimientos (licencias, planes, DR obras) |
| Planeamiento CARM (consulta) | https://urbmurcia.carm.es/urbmurcia/faces/pla/query.jsp | Consulta expedientes planeamiento (complementario) |

## Proyectos / expedientes

- **Tablón sede:** paginación `?page=N`; título en `<p class="fw-bold">`, fecha en `<time datetime>`, PDF con `aria-label`.
- **infourb Ultimas.aspx:** HTML estático con secciones MODIFICACIONES PG, PLANEAMIENTO DE DESARROLLO, PROYECTOS DE GESTIÓN; cada bloque incluye expediente (`NNNN/YYYY/PL`) y enlace a documentación digitalizada.

## Licencias

- No hay dataset público de concesiones; el tablón puede publicar edictos de licencia puntuales.
- Trámites informativos: sede categoría 10001, fichas 263 (licencia ordinaria), 5422 (obra menor), etc.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Geovisor: https://geovisor.murcia.es/
  - WMS/WFS: `https://callejero.murcia.es/wms` y `https://callejero.murcia.es/wfs`
  - Capa sectores PGMO: `urbanismo:sectores` (campo `nombre_cod`, p. ej. `ZM-SS1-1`, `ZG-SG-CT6`)
- **Estrategia:** extraer códigos de sector del título (tablón / infourb) y consultar WFS `GetFeature` con `srsName=EPSG:4326`; centroide del polígono.
- **Limitaciones:** no todos los códigos citados en anuncios existen en la capa (p. ej. `ZU-SD-CT12` ausente en WFS al scrapear); licencias sin parcela en GIS; infourb sin geometría por expediente.

## Limitaciones generales

- Carpeta ciudadana / estado de expediente requiere autenticación.
- infourb usa HTTP en `urbanismo.murcia.es` (redirección desde portal).
- Tablón mezcla edictos no urbanísticos; el adapter filtra por regex.
