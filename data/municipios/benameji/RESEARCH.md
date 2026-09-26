# Benamejí — investigación portal ayuntamiento

**Municipio:** Benamejí (Córdoba, Andalucía)  
**Slug:** `benameji`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 14009

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://benameji.es | **Operativa** — WordPress Divi v4 (eprinsa/Diputación Córdoba) |
| Documentos / normativa | https://benameji.es/ayuntamiento/ayuntamiento-documentos/ | **Operativa** — ~111 PDFs (ordenanzas, convenios, modelos licencia) |
| PGOU | https://drive.google.com/file/d/12r5tqom9aiJMIADEh8r8vhi5ZbbpvcDV/view | Enlace desde documentos (Google Drive) |
| Sede electrónica | https://sede.eprinsa.es/benameji | **Operativa** — plataforma eprinsa, Ember.js SPA |
| Tablón de edictos | https://sede.eprinsa.es/benameji/tablon-de-edictos | **SPA** — componente `wec-bulletins`; requiere token de sesión |
| Catálogo trámites | https://sede.eprinsa.es/benameji/tramites | Trámites administrativos (sin histórico de licencias) |
| Consulta expedientes | https://sede.eprinsa.es/benameji/expedientes | Requiere autenticación Cl@ve/certificado |
| Post obras | https://benameji.es/declaracion-responsable-para-realizacion-de-obras/ | Informativo (enlace a documentos) |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress Divi + Toolset (eprinsa).
- **Sin sección urbanismo dedicada** en el menú; la normativa y modelos están en `ayuntamiento-documentos`.
- **Contenido scrapeable:**
  - PGOU (Google Drive).
  - Relación de convenios formalizados (PDFs 2021–2025).
  - Ordenanzas urbanísticas (actuaciones, suelo, instrumentos de intervención, registro municipal).
  - Modelos de solicitud: licencias de obra (anexo I), parcelación (II), declaración responsable (III), comunicación previa (V).
- **WP REST API:** posts accesibles (`/wp-json/wp/v2/posts`); sin categoría urbanismo explícita.
- **Tablón eprinsa:** edictos de información pública y licencias deberían publicarse aquí, pero el listado es SPA sin API REST pública.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Modelos de solicitud en documentos (anexos I–V, 2023).
- Edictos de licencias en tablón eprinsa (no scrapeable sin sesión).
- Trámites vía sede (`/tramites`) y consulta de expedientes con autenticación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - CSP de benameji.es permite `mapserver.eprinsa.es` en iframes, pero no hay visor urbanístico enlazado desde la web municipal.
  - VITUA (Junta de Andalucía): https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ — cartografía LISTA/PGOU por municipio; sin campo expediente del ayuntamiento.
  - SITUA: https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf — documentación de instrumentos autonómicos; sin query por código de expediente municipal.
- **Estrategia:** VITUA/SITUA muestran clasificación del PGOU vigente, pero **no enlazan** con filas del tablón ni PDFs de la sede. Los anuncios son PDF/texto sin georreferencia embebida.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST accesible por expediente desde el portal municipal.
  - Tablón SPA sin API pública.
  - PGOU en Google Drive (PDF sin coords).
  - El orquestador aplicará centroide municipio + jitter (`centroid: [37.2683, -4.5417]`).

## Limitaciones generales

- Tablón eprinsa no scrapeable determinísticamente (token de sesión).
- Sin visor de seguimiento de expedientes urbanísticos público fuera del tablón/sede autenticada.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.benameji:BenamejiAyuntamientoAdapter`
- Fuentes: página documentos (proyectos PDF + PGOU Drive) + páginas informativas sede eprinsa (licencias) + posts WP.
