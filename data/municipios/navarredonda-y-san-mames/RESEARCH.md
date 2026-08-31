# Navarredonda y San Mamés — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://navarredondaysanmames.org | OK (WordPress + Avada) |
| Urbanismo | https://navarredondaysanmames.org/urbanismo/ | OK (contacto técnico, sin listado) |
| Descarga documentos | https://navarredondaysanmames.org/descarga-de-documentos/ | OK (PDFs licencias) |
| PGOU / avance | https://navarredondaysanmames.org/pgou-plan-general-de-ordenacion-urbanistica-de-navarredonda-y-san-mames/ | OK |
| Sede electrónica | https://sedenavarredondaysanmames.eadministracion.es | OK (Maggioli SPA) |
| Tablón sede | https://sedenavarredondaysanmames.eadministracion.es/PortalCiudadano/Tablon/wfrTablon.aspx | OK (requiere JS) |
| Transparencia eAdmin | https://transparencianavarredondaysanmames.eadministracion.es/portal | No disponible (portalNoDisponible) |
| Portal transparencia WP | https://navarredondaysanmames.org/portal-de-transparencia/ | OK (presupuestos/plenos, sin urbanismo) |

## Proyectos / expedientes

- **CMS:** WordPress con REST API (`/wp-json/wp/v2/posts`, ~750 entradas)
- **Listado:** noticias filtradas por keywords (PGOU, licencia, obra, BOCM, urbanización)
- **Semillas estáticas:** avance PGOU (mar 2025), información pública PGOU, consultas PGOU
- **PDFs:** `Informacion-al-publico-PGOU.pdf`, `Solicitud-cita-consulta-PGOU.pdf` en posts PGOU
- **Histórico:** licitación urbanización Calleja de los Avellanos (2017), licencia actividad bar social (BOCM 2023)
- **Sede eAdmin:** tablón Angular sin HTML scrapeable; anuncios BOCM publicados también en web

## Licencias de obra

- No hay dataset abierto de concesiones con coordenadas
- Formularios en `/descarga-de-documentos/`:
  - `Impreso-DRUO-Licencia-de-Obras.pdf`
  - `SOLICITUD-DE-LICENCIA-DE-OBRA.pdf`
  - `INSTANCIA-GENERAL-.pdf`
- Trámites telemáticos vía sede eAdmin Maggioli
- Anuncios puntuales en noticias (licencia actividad bar social San Mamés, BOCM 2023)

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** ninguna pública enlazable
  - SITCM WFS `sitcm:VPLA_V_AMBITO`: sin features para `DS_MUNICIPIO='NAVARREDONDA Y SAN MAMÉS'`
  - Sin visor urbanístico municipal ni datos abiertos GeoJSON
  - PDFs PGOU sin georreferencia embebida
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [40.992747, -3.708756]`)
- **Limitaciones:**
  - Municipio en tramitación de primer PGOU (avance 2025); no hay planeamiento aprobado en SITCM
  - Sede eAdmin y tablón requieren JavaScript
  - Portal transparencia eAdmin deshabilitado

## Limitaciones generales

- Web muy orientada a noticias generales (~750 posts); filtro estricto por keywords urbanísticas
- Dominio `.madrid` en correo técnico pero web en `.org`
- User-Agent identificable; `insecure_ssl: true` por compatibilidad sede eAdmin
