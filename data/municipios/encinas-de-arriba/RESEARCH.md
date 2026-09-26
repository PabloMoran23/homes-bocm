# Encinas de Arriba — investigación portal ayuntamiento

**Municipio:** Encinas de Arriba (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-15  
**BOCYL (referencia):** 1 aviso  
**INE:** 37122 | **DIR3:** L01371226 | **CIF:** P3712200I

## Resumen

Encinas de Arriba es un municipio pequeño (~235 hab.) de la Tierra de Alba. La web
`www.encinasdearriba.es` **no responde** en el entorno del agente (timeout / sin contenido).
Toda la gestión digital pasa por la **sede electrónica espublico gestiona**
(`encinasdearriba.sedelectronica.es`). El planeamiento vigente es un **DSU** (Delimitación de
Suelo Urbano) aprobado en 1987, centralizado en **PlanPublica / SiuCyL**. No hay visor
urbanístico municipal ni listado público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa (inactiva) | http://www.encinasdearriba.es | Sin respuesta HTTP |
| Sede electrónica (inicio) | https://encinasdearriba.sedelectronica.es/info.0 | Requiere cookie de sesión previa |
| Tablón de anuncios | https://encinasdearriba.sedelectronica.es/board | Responde; sin anuncios urbanísticos (sep 2026) |
| Catálogo de trámites | https://encinasdearriba.sedelectronica.es/dossier/.0 | ~74 KB tras warm-up en `/board`; 113 trámites |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=122 | 1 documento (DSU 1987) |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=122 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37122 | Mapa interactivo regional |

**Contacto:** C/ Institución 3, 37892 Encinas de Arriba · Tel. 923 371 283 · ayuntencinasarriba@hotmail.com

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **DSU** (Delimitación de Suelo Urbano — normativa anterior), aprobación **19/02/1987**
  (`cDocId=278423`, código `37122-PU-A19870219-278423`).
- Sin NUM, planes parciales ni sectores en IDECyL WFS (ago 2026).

### Listado PlanPublica (PLAU)

Tabla HTML con una fila:

| Campo | Valor |
|-------|-------|
| Tipo | PU |
| Subtipo | DSU |
| Fecha | 19/02/1987 |
| Título | DSU |
| PDF | `openDocuIndice.do?cDocId=278423` |

### Tablón / sede

- Tablón accesible pero **vacío** de `preview-document` (sin licencias ni IP publicadas).
- Catálogo de trámites incluye páginas informativas de licencias y planeamiento (UUID estándar espublico).

## 3. Licencias

No hay concesiones publicadas en tablón. El adapter recoge **páginas informativas** del catálogo:

- Declaración Responsable o Comunicación en Materia Urbanística
- Solicitud de Modificación o Renuncia de una Licencia Urbanística
- Solicitud de Licencia de Ocupación
- Solicitud de Certificado o Informe Urbanístico
- (y otras licencias de actividad / ocupación)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` filtro `c_mun='37122'` o `n_mun='Encinas de Arriba'`
  - 1 feature: DSU «Delimitación de Suelo Urbano» — `MultiPolygon` EPSG:4326
  - SiUR: https://idecyl.jcyl.es/siur/index.html?id=37122
- **Estrategia:** query WFS GetFeature `outputFormat=application/json&srsName=EPSG:4326`; enlazar geometría del instrumento a filas PLAU/WFS; sectores = 0 capas
- **Limitaciones:** sin visor municipal; sin geometría por expediente/licencia individual; tablón sin PDFs georreferenciables; web corporativa caída

## 4. Limitaciones técnicas

| Limitación | Impacto |
|------------|---------|
| Web corporativa inactiva | Solo sede + JCyL como fuentes |
| Sede dossier requiere warm-up (`/board` → cookie) | Primera petición a `dossier/.0` puede timeout sin sesión |
| SSL sede con certificado problemático en algunos entornos | `insecure_ssl: true` en manifest |
| Sin sectores WFS | Geometría solo a nivel municipio/DSU |
| Sin licencias en tablón | Solo trámites informativos |

## 5. Referencias de implementación

- Adapter hermano: `municipio/adapters/valverdon.py` (mismo patrón espublico + PLAU + WFS CYL)
- Helpers geometría: `municipio/geometry.py`
