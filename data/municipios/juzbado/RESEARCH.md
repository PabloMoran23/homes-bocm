# Juzbado — investigación portal ayuntamiento

**Municipio:** Juzbado (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-19  
**BOCYL (referencia):** 1 aviso  
**INE:** 37167

## Resumen

Juzbado publica urbanismo a través de **tres canales**: web corporativa WordPress/Kubio
(`juzbado.es/nuevaweb`), **sede electrónica espublico gestiona** (`juzbado.sedelectronica.es`)
y el archivo regional **PlanPublica / SiuCyL**. El planeamiento vigente son las **Normas Subsidiarias
de Planeamiento Municipal** (NSPM, 1989) con 4 sectores de suelo urbanizable en IDECyL WFS.
No hay listado público de concesiones de licencias georreferenciadas; el tablón de anuncios está
casi vacío (solo avisos administrativos no urbanísticos).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web municipal | https://juzbado.es/nuevaweb/ | WordPress + Kubio; certificado SSL caducado en `www.juzbado.es` |
| Agenda Urbana | https://juzbado.es/nuevaweb/agenda-urbana-de-juzbado/ | Documentación participación ciudadana |
| Ordenanzas | https://juzbado.es/nuevaweb/ordenanzas/ | Enlaza agenda urbana |
| Blog legacy urbanismo | https://juzbado.blogspot.com/p/urbanismo.html | Modelos PDF en Google Drive |
| Sede electrónica | https://juzbado.sedelectronica.es/info.0 | espublico gestiona (Wicket); lento |
| Tablón de anuncios | https://juzbado.sedelectronica.es/board/ | Vacío de urbanismo (sep 2026) |
| Catálogo trámites | https://juzbado.sedelectronica.es/dossier/.0 | Requiere cookie; ~45 s primera carga |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=167 | 1 documento NSPM |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=167 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37167 | Mapa interactivo regional |

**Contacto:** Calle Consistorial 5, 37115 Juzbado · Tel. 923 32 13 36 · juzbadoayuntamiento@gmail.com

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NSPM** (Normas Subsidiarias de Planeamiento Municipal), aprobación **04/05/1989** (`cDocId=278471`).
- Sectores en WFS: Sector 1 (residencial SUR), Sector 2 (residencial SUR), Sector 3 (industrial SUR), Sector 4.

### PlanPublica (PLAU)

Tabla HTML con fila única:

| cDocId | Código | Fecha | Título |
|--------|--------|-------|--------|
| 278471 | 37167-PU-A19890505-278471 | 04/05/1989 | NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL |

### Sede electrónica — trámites urbanísticos

Catálogo dossier (sección 3.01.00 Urbanismo y Vivienda) incluye, entre otros:

- Declaración Responsable o Comunicación en Materia Urbanística
- Solicitud de Licencia o Autorización Urbanística
- Solicitud de Modificación o Renuncia de Licencia Urbanística
- Solicitud de Licencia de Ocupación
- Solicitud de Certificado o Informe Urbanístico
- Modificación del Planeamiento de Desarrollo / Planeamiento General
- Solicitud de Actuación Urbanística

Son páginas informativas de trámite (no concesiones publicadas).

### Blog urbanismo — modelos

Formularios en Google Drive:

- Declaración responsable actos de uso del suelo no sometidos a licencia urbanística
- Modelo solicitud corral doméstico
- Modificación no sustancial de actividad sujeta a licencia o comunicación ambiental

## 3. Licencias de obra

- **Tablón sede:** sin licencias publicadas (solo aviso jurado popular, no urbanismo).
- **Trámites:** catálogo sede + modelos blogger (páginas informativas).
- No hay dataset ni visor de licencias con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — filtro `c_mun='37167'` (4 polígonos MultiPolygon)
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono NSPM
  - SiuCyL SiUR: https://idecyl.jcyl.es/siur/index.html?id=37167
- **Estrategia:** query WFS con `srsName=EPSG:4326`; enriquecer proyectos de sectores/PLAU con `geom_geojson`.
- **Limitaciones:** sin visor municipal propio; licencias sin georreferenciación; SSL caducado en dominio raíz (`insecure_ssl` en adapter).

## 4. Limitaciones

- Certificado SSL inválido en `juzbado.es` (funciona `juzbado.es/nuevaweb` con verificación desactivada).
- Sede `info.0` muy lenta; tablón y dossier más fiables.
- PLAI sin documentos activos.
- Sin PGOU/NUM reciente; instrumento histórico NSPM 1989.

## 5. Estrategia adapter

1. **Proyectos:** IDECyL WFS (sectores + instrumento) + PLAU JCyL + agenda urbana WP + trámites sede.
2. **Licencias:** trámites catálogo sede + formularios blogger (informativos).
3. **Geometría:** WFS sectores/instrumento → `geom_geojson` en WGS84.
4. **IDs:** `juzbado-{lic|proy}-{sha256[:14]}`.
