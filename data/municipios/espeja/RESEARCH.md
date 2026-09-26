# Espeja — investigación portal ayuntamiento

**Municipio:** Espeja (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-15  
**BOCYL (referencia):** 1 aviso  
**INE:** 37127 | **CIF:** P3712700H

## Resumen

Espeja dispone de **web corporativa WordPress** (`aytoespeja.es`, redirige desde `www.espeja.es`) y
**sede electrónica espublico gestiona** (`espeja.sedelectronica.es`). El planeamiento urbanístico
vigente es un **DSU** (Delimitación de Suelo Urbano, 1994) publicado en **PlanPublica / SiuCyL**.
No hay listado público de concesiones de licencias georreferenciadas; el tablón de anuncios de la
sede publica avisos administrativos generales (presupuesto, IAE, edictos).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://aytoespeja.es | WordPress; categoría tablón de anuncios |
| Sede electrónica (inicio) | https://espeja.sedelectronica.es/info.0 | Redirige desde `www.espeja.es` |
| Tablón de anuncios | https://espeja.sedelectronica.es/board/ | 5 anuncios (sep 2026); sin urbanismo |
| Catálogo de trámites | https://espeja.sedelectronica.es/dossier/.0 | Requiere warm-up `/board/` + cookie de sesión |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=127 | 1 documento (DSU 1994) |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=127 | Sin documentos activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37127 | Mapa interactivo regional |

**Contacto:** Plaza 3, 37497 Espeja · Tel. 923 483 837 · espeja_es@hotmail.com

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **DSU** (Delimitación de Suelo Urbano), aprobación **26/05/1994**, publicación BOCYL **10/11/1994**
  (`cDocId=278427`).
- Sin sectores de desarrollo ni planes parciales activos en IDECyL.

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Documento identificado:

| cDocId | Código | Fecha | Título |
|--------|--------|-------|-------|
| 278427 | 37127-PU-19940526-278427 | 10/11/1994 | DSU |

**Endpoints:**

```
GET https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=127
GET https://servicios.jcyl.es/PlanPublica/openDocumento.do?cDocId=278427
```

### Tablón de anuncios (sede)

Tabla HTML con columnas: documento, expediente, procedimiento, categoría, descripción, fecha.
Enlaces a `preview-document/{uuid}`. Contenido actual: edictos notariales, delegación de alcalde,
presupuesto, cobranza IAE — **sin licencias ni expedientes urbanísticos**.

### Catálogo de trámites (sede)

~114 trámites en `dossier/.0`. Trámites urbanísticos relevantes (UUIDs compartidos plataforma espublico):

- Declaración Responsable o Comunicación en Materia Urbanística
- Solicitud de Licencia o Autorización Urbanística
- Modificación del Planeamiento de Desarrollo
- Solicitud de Actuación Urbanística
- Solicitud de Certificado o Informe Urbanístico

Son páginas informativas de trámite; no publican concesiones.

## 3. Licencias de obra

No hay dataset ni tablón con licencias concedidas georreferenciadas. El adapter devuelve:

1. Entradas del tablón si aparecen licencias (actualmente ninguna).
2. Páginas informativas de trámites de licencia del catálogo sede.

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — filtro `n_mun='Espeja'`
  - SiuCyL visor: https://idecyl.jcyl.es/siur/index.html?id=37127
- **Estrategia:** query WFS GetFeature con `outputFormat=application/json`, `srsName=EPSG:4326`;
  1 MultiPolygon del ámbito DSU; sin sectores (`plau_cyl_sectores`: 0 features) ni planes parciales.
- **Limitaciones:** instrumento histórico DSU sin sectores de desarrollo; licencias sin geometría;
  tablón sin coords; sede requiere `insecure_ssl` y warm-up de sesión.

## 4. Limitaciones

- Certificado SSL de la sede con cadena no verificable → `insecure_ssl: true`.
- `dossier/.0` requiere visita previa a `/board/` para obtener cookie de sesión.
- Sin visor urbanístico municipal propio; geometría solo a nivel de instrumento DSU.
- Web corporativa tablón es categoría WordPress, no fuente estructurada de expedientes.

## 5. Estrategia del adapter

Patrón hermano de Valverdón / Encinas de Arriba (CYL/Salamanca):

1. Tablón + info tablón de la sede espublico.
2. Catálogo de trámites urbanísticos (páginas informativas).
3. PlanPublica PLAU (documentos aprobados).
4. IDECyL WFS (polígono DSU + enriquecimiento por código de sector si aparece en título).
