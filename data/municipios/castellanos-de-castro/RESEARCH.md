# Castellanos de Castro — investigación portal ayuntamiento

**Municipio:** Castellanos de Castro (provincia Burgos, Castilla y León)  
**Fecha:** 2026-09-11  
**BOCYL (referencia):** 1 aviso  
**INE:** 09079 | **PlanPublica municipio:** 089 (provincia 09)

## Resumen

Municipio pequeño (<100 hab.) con **web corporativa Drupal 10** (tema Toools, `castellanosdecastro.es`) y
**sede electrónica espublico gestiona** (`castellanosdecastro.sedelectronica.es`). No dispone de PGOU/NUM
propio: el instrumento vigente registrado en JCYL es **Sin Planeamiento General (SPG)**. No hay visor
urbanístico municipal; la geometría del término municipal está en **IDECyL WFS**.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web municipal | https://castellanosdecastro.es/inicio | Drupal 10, menú megamenu Toools |
| Normativa | https://castellanosdecastro.es/normativa | Sin PDFs urbanísticos indexados |
| Sede electrónica | https://castellanosdecastro.sedelectronica.es/ | espublico gestiona (Wicket); certificado SSL inválido |
| Tablón de anuncios | https://castellanosdecastro.sedelectronica.es/board | Vacío (sep 2026) |
| Transparencia | https://castellanosdecastro.sedelectronica.es/transparency | Sección 7 «Urbanismo…» con **0** documentos |
| Catálogo trámites | https://castellanosdecastro.sedelectronica.es/dossier/.0 | Timeout frecuente (>60 s); UUIDs estándar espublico en `/catalog/t/{uuid}` |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=089 | Sin filas en tabla (instrumento SPG solo en WFS) |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=089 | Sin documentos activos |
| SiUR visor | https://idecyl.jcyl.es/siur/index.html?id=09079 | Visor regional JCYL |
| Diputación Burgos | https://www.burgos.es/provincia/municipio/castellanos-de-castro | Ficha municipal |

**Contacto:** Plaza Mayor 1, 09227 · Tel. 947 378 582 · castellanosdecastro@diputaciondeburgos.net

## 2. Planeamiento / expedientes

### Instrumento vigente (WFS IDECyL)

- **SPG** — Sin Planeamiento General (`c_plan=09079-PU-00000000-276694`, `cDocId=276694`).
- Documentación: https://servicios.jcyl.es/PlanPublica/openDocuIndice.do?cDocId=276694
- Polígono municipal en WFS `plau_cyl_instrumentos_ambito` (~9,9 km²).
- **0** sectores (`plau_cyl_sectores`) y **0** planes parciales.

### Tablón / transparencia

- Tablón espublico sin filas visibles.
- Transparencia urbanismo vacía.

### Catálogo trámites (espublico)

UUIDs estándar de la plataforma (compartidos con otros ayuntamientos espublico):

| Trámite | URL |
|---------|-----|
| Declaración Responsable / Comunicación urbanística | `/catalog/t/5d383e20-32a5-4fcf-8725-e51c51e83e6a` |
| Solicitud Licencia o Autorización Urbanística | `/catalog/t/15fabacb-83b1-47d1-b435-508245672051` |
| Modificación / Renuncia Licencia | `/catalog/t/a3c783fb-bb19-4ea3-b40f-0072d69aebae` |
| Licencia de Ocupación | `/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Certificado / Informe Urbanístico | `/catalog/t/e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |
| Modificación Planeamiento de Desarrollo | `/catalog/t/6e8237a3-0b83-469d-b0ad-70159b9a9c26` |
| Planeamiento General (Modificación) | `/catalog/t/96514574-aca1-40e1-a800-e06485e6d016` |
| Solicitud Actuación Urbanística | `/catalog/t/f91e4a50-d23d-45c1-a19b-b148da37c59f` |

Son formularios informativos; no hay histórico de concesiones georreferenciadas.

## 3. Licencias de obra

No hay listado público de licencias concedidas. El adapter modela páginas de trámite del catálogo espublico
(patrón Valverdón / Pozuelo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` filtrado `n_mun='Castellanos de Castro'`;
  capas `plau_cyl_sectores` y `plau_cyl_planes_parciales` vacías.
- **Estrategia:** query WFS GeoJSON (`outputFormat=application/json`, `srsName=EPSG:4326`); centroide del
  polígono SPG para coordenadas; SiUR como referencia visual (`id=09079`).
- **Limitaciones:** sin visor municipal; tablón/transparencia sin GIS; licencias sin coordenadas; sede con SSL
  inválido (`insecure_ssl: true`).

### Ejemplo WFS

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_instrumentos_ambito
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='Castellanos de Castro'
```

## Limitaciones

- Municipio sin planeamiento detallado (solo SPG).
- Tablón y transparencia urbanismo vacíos.
- `/dossier/.0` muy lento; se usan UUIDs de catálogo conocidos.
- Certificado SSL de la sede requiere `insecure_ssl`.

## Estrategia adapter

1. **WFS IDECyL** → proyecto SPG con `geom_geojson` (MultiPolygon término municipal).
2. **PlanPublica PLAU/PLAI** → parseo tabla HTML (vacío actualmente).
3. **Tablón sede** → filas urbanismo/licencia si aparecen.
4. **Catálogo trámites** → licencias/proyectos informativos (UUIDs espublico).
5. **IDs:** `castellanos-de-castro-{lic|proy}-{sha256[:14]}`.
