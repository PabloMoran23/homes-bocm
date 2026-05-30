import { ImageResponse } from "next/og";

export const alt = "Homes · Urbanismo Madrid";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          background: "linear-gradient(145deg, #f0fdfa 0%, #ffffff 45%, #f8fafc 100%)",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 14,
              background: "#0f766e",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "white",
              fontSize: 28,
              fontWeight: 700,
            }}
          >
            H
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: 28, fontWeight: 700, color: "#0f172a" }}>Homes</span>
            <span style={{ fontSize: 22, color: "#0f766e", fontWeight: 600 }}>Urbanismo Madrid</span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 900 }}>
          <div
            style={{
              fontSize: 52,
              fontWeight: 700,
              color: "#0f172a",
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
            }}
          >
            Proyectos urbanísticos en tu zona
          </div>
          <div style={{ fontSize: 26, color: "#475569", lineHeight: 1.4 }}>
            Licencias, planeamiento SIGMA y anuncios BOCM en un mapa unificado de Madrid capital.
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 22, color: "#0f766e", fontWeight: 600 }}>homes-urbanismo.es</span>
          <span style={{ fontSize: 18, color: "#94a3b8" }}>Mapa · Boletín · Estadísticas</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
