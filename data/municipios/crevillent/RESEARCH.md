# Crevillent — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web corporativa | https://crevillent.es |
| Oficina técnica | https://crevillent.es/area/oficina-tecnica/ |
| Documentos planeamiento (PGOU, planos PDF) | https://crevillent.es/seccion/documentos-de-la-oficina-tecnica/ |
| Sede electrónica (Sedipualba) | https://crevillent.sedipualba.es |
| Catálogo trámites urbanismo (área 1547) | https://crevillent.sedipualba.es/catalogoservicios.aspx?ambito=&area=1547 |
| Tablón de anuncios | https://crevillent.sedipualba.es/tablondeanuncios/ |
| Tablón RSS | https://crevillent.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Índice planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03059%20CREVILLENT/ |

## Expedientes / planeamiento

- **Web WordPress:** listado estático de PDFs del Plan General (memoria, normas, planos de ordenación, sectores R-3, R-5, I-10, etc.). No hay visor municipal de expedientes abiertos; la información pública de modificaciones puntuales aparece en el **tablón** (títulos tipo `MP 29-2026 SC 5`).
- **Sede Sedipualba:** catálogo de procedimientos URB (licencias, declaraciones responsables, certificados). Son páginas informativas de trámite, no un registro de expedientes resueltos.
- **Tablón RSS:** feed ISO-8859-1 con anuncios recientes; filtrado por palabras clave urbanísticas.

## Licencias de obra

- No hay listado público de licencias concedidas (concesiones).
- Trámites disponibles: `URB-LOED`, `URB-DREO`, `URB-DROM`, declaraciones responsables, licencias en suelo no urbanizable, etc. (catálogo área 1547).
- El adapter ingiere **páginas de trámite** como filas informativas (patrón Pozuelo/Paiporta) y edictos del tablón que mencionen licencias.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento` filtrado por `cod_ine_mun=03059` (sectores SU/SUZ con polígonos EPSG:4326).
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz
  - Planos PDF del PGOU en la web municipal (sin georreferencia vectorial enlazable a expediente).
- **Estrategia:** paginar WFS InventarioSuSuz; enriquecer proyectos del tablón/web por coincidencia de tokens sector/UE/MP; centroide del polígono cuando hay match.
- **Limitaciones:** WFS no enlaza códigos de expediente del tablón; licencias sin geometría; visor municipal inexistente.

## Limitaciones generales

- Sin API de expedientes urbanísticos.
- Tablón mezcla RRHH, fiscalidad y urbanismo (filtrado heurístico).
- RSS en `iso-8859-1` (decodificación latin-1).
