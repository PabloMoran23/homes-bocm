# Ledesma — investigación portal ayuntamiento

**Municipio:** Ledesma (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-08-20  
**BOCYL (referencia):** 3 avisos  
**INE:** 37170 | **DIR3:** L01371703

## Resumen

Ledesma dispone de **web corporativa Angular** (`ayuntamientodeledesma.com`, SPA sin listados
urbanísticos scrapeables) y **sede electrónica espublico gestiona** (`ledesma.sedelectronica.es`).
El planeamiento urbanístico vigente (NUM, planes parciales UBZ/SNC, casco histórico) está en
**PlanPublica / SiuCyL**. La geometría de sectores está en **WFS IDECyL** (29 polígonos).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://www.ayuntamientodeledesma.com | Angular SPA; sin listado expedientes |
| Sede electrónica | https://ledesma.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://ledesma.sedelectronica.es/board/ | ~10 filas; licencias urbanísticas y actividad |
| Catálogo de trámites | https://ledesma.sedelectronica.es/dossier/.0 | Lento (>60 s); formularios |
| PlanPublica — archivo aprobado | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=170 | 16+ documentos |
| PlanPublica — información pública | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=170 | Sin documentos activos (ago 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37170 | Visor regional |
| Información urbanística Diputación | http://www.lasalina.es/...?codMunicipio=170 | Ficha municipal |

**Contacto:** Plaza Mayor 1, 37100 Ledesma · Tel. 923 57 00 15 · informacion@ayuntamientodeledesma.com

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación 2005 (modificaciones hasta 2012).
- **Plan Especial del Casco Histórico** (PECH).
- Múltiples **planes parciales** sectores UBZ-1 a UBZ-15 y sectores SNC (suelo no consolidado).
- Modificación Nº 7 NUM (suelo rústico) publicada en BOCYL oct 2025.

### Listado PlanPublica (PLAU)

Tabla HTML con filas `PU|GU|EU|SU` + subtipo (NUM, PP, PECH, PAU…). Enlaces vía `doOpen(cDocId)`.

Documentos destacados: NUM original, PECH, PP UBZ-1/2/6/8/9/15, modificaciones NUM, proyectos urbanización UBZ-2.

Códigos PlanPublica: **provincia=37**, **municipio=170**.

## 3. Building licenses — tablón, sede

### Tablón (`/board/`)

Tabla espublico con licencias publicadas:

- Autorizaciones excepcionales en suelo rústico (parcelas 5013 pol. 501, parcela 19 pol. 2).
- Categorías: «Licencias Urbanísticas», «Licencias de Actividad».
- PDFs: `preview-document/{uuid}`.

### Catálogo trámites

Formularios informativos (mismos UUID espublico que otros municipios CyL):

- Solicitud de Licencia o Autorización Urbanística
- Declaración Responsable o Comunicación en Materia Urbanística
- Modificación del Planeamiento, etc.

**No hay** dataset histórico de concesiones georreferenciadas.

## 4. GIS / geometría

| Fuente | URL | Contenido Ledesma |
|--------|-----|-------------------|
| WFS sectores | `urbanismo:plau_cyl_sectores` + `n_mun='Ledesma'` | **29 polígonos** (UBZ-*, SNC-*) |
| WFS instrumentos | `urbanismo:plau_cyl_instrumentos_ambito` | 1 polígono NUM municipal |
| SiUR visor | `idecyl.jcyl.es/siur/index.html?id=37170` | Visor regional (no API directa) |

**No hay** visor urbanístico municipal propio ni ArcGIS local.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS IDECyL `plau_cyl_sectores` (29 features UBZ/SNC) + `plau_cyl_instrumentos_ambito` (NUM).
- **Estrategia:** extraer códigos `UBZ-n`, `SNC-n` del título PlanPublica/tablón → query WFS por `n_num_sect`;
  fallback polígono NUM para documentos sin sector explícito.
- **Limitaciones:** licencias del tablón sin coordenadas; web Angular no scrapeable; sede requiere `insecure_ssl`.

## Limitaciones

- Web corporativa SPA sin endpoints públicos de expedientes.
- Tablón: ventana corta (~10 anuncios).
- `/dossier` muy lento; catálogo es informativo.
- Licencias sin geometría puntual en portal.

## Estrategia adapter

1. **PlanPublica PLAU** → parsear tabla HTML (`doOpen`, títulos, fechas).
2. **WFS IDECyL** → geometría por sector y ámbito NUM.
3. **Tablón sede** → licencias y proyectos de autorización en suelo rústico.
4. **Catálogo trámites** → páginas informativas de licencia/planeamiento.
5. **IDs:** `ledesma-{lic|proy}-{sha256[:14]}`.
