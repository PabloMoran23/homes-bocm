# El Espinar — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León). El ayuntamiento publica su web corporativa en **WordPress** (`elespinar.es`, tema egovt). La **sede electrónica** es **espublico gestiona** (`elespinar.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa | https://elespinar.es |
| Urbanismo | https://elespinar.es/urbanismo/ |
| PGOU (aprobación definitiva parcial) | https://elespinar.es/aprobacion-definitva-parcial-del-pgou-de-el-espinar/ |
| Sede electrónica | https://elespinar.sedelectronica.es |
| Tablón sede | https://elespinar.sedelectronica.es/board/ |
| Información pública sede | https://elespinar.sedelectronica.es/info.0 |
| Trámites (catálogo) | https://elespinar.sedelectronica.es/dossier |
| Archivo PLAU (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=135 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=135 |

## Expedientes / planeamiento

- **Urbanismo en web:** página WordPress con enlaces al PGOU, convenio urbanístico sector 1.8B (PDF), estatutos y sentencias; contacto `urbanismo@aytoelespinar.com`.
- **PLAU JCYL:** tabla HTML paginada con documentos aprobados (NUM de 2018–2020: normas urbanísticas, aplicación art. 56.2 Ley 5/1999, sentencia TSJ polígono 16).
- **Tablón sede:** tabla HTML Wicket con `preview-document/…`; incluye anuncios de declaraciones/comunicaciones urbanísticas y uso excepcional de suelo rústico.
- **Sin visor municipal propio** ni listado JSON de expedientes en curso.

## Licencias de obra

- Trámites en sede espublico (`/dossier`, catálogo `/catalog/t/…`); el catálogo devuelve bucle de redirección 302 desde algunos entornos.
- No hay dataset público de licencias concedidas con coordenadas.
- El tablón publica anuncios puntuales (p. ej. autorización uso excepcional suelo rústico / corral).
- El adapter incluye entradas del tablón y páginas informativas de trámites.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'El Espinar'`:
  - `urbanismo:plau_cyl_instrumentos_ambito` (1 feature: PGOU MultiPolygon)
  - `urbanismo:plau_cyl_planes_parciales` (5 features)
  - `urbanismo:plau_cyl_sectores` (16 features: SE1–SE22b, MARIGARCIA, LAS HUERTAS, etc.)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de título/sector en filas PLAU, WordPress y tablón.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin polígono; expedientes del tablón no siempre enlazan a sector WFS.

## Limitaciones generales

- `/dossier` de la sede puede entrar en bucle de redirección; el adapter tolera timeout y usa tablón + WordPress + PLAU.
- Sin API JSON de expedientes; scrape determinista HTML + WFS + PLAU.
- Contacto urbanismo: `oficinaurbanismo@aytoelespinar.com`, `urbanismo@aytoelespinar.com`.
