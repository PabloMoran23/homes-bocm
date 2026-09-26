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
          background: "linear-gradient(145deg, #f7f3eb 0%, #f4efe6 48%, #ebe4d6 100%)",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 14,
              background: "#1f4f53",
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
            <span style={{ fontSize: 28, fontWeight: 700, color: "#2a2622" }}>Homes</span>
            <span style={{ fontSize: 22, color: "#1f4f53", fontWeight: 600 }}>Urbanismo Madrid</span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 900 }}>
          <div
            style={{
              fontSize: 52,
              fontWeight: 700,
              color: "#2a2622",
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
            }}
          >
            Qué se está moviendo cerca de ti
          </div>
          <div style={{ fontSize: 26, color: "#6a6158", lineHeight: 1.4 }}>
            Obras, planes y actividad urbanística en Madrid capital — mapa, tu calle y dashboard.
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 22, color: "#1f4f53", fontWeight: 600 }}>homes-urbanismo.es</span>
          <span style={{ fontSize: 18, color: "#8a8278" }}>Mapa · Tu zona · Dashboard</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
