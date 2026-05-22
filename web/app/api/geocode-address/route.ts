import { NextResponse } from "next/server";

const MADRID_BOUNDS = {
  minLat: 40.31,
  maxLat: 40.65,
  minLng: -3.9,
  maxLng: -3.5,
};

type NominatimResult = {
  lat?: string;
  lon?: string;
  display_name?: string;
  address?: {
    city?: string;
    town?: string;
    village?: string;
    municipality?: string;
    suburb?: string;
    quarter?: string;
    neighbourhood?: string;
    road?: string;
    house_number?: string;
  };
};

function isInMadrid(lat: number, lng: number) {
  return (
    lat >= MADRID_BOUNDS.minLat &&
    lat <= MADRID_BOUNDS.maxLat &&
    lng >= MADRID_BOUNDS.minLng &&
    lng <= MADRID_BOUNDS.maxLng
  );
}

function readableLabel(result: NominatimResult, fallback: string) {
  const a = result.address;
  const street = [a?.road, a?.house_number].filter(Boolean).join(" ");
  const area = a?.suburb || a?.quarter || a?.neighbourhood;
  const city = a?.city || a?.town || a?.village || a?.municipality;
  return [street || fallback, area, city].filter(Boolean).join(" · ");
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const q = url.searchParams.get("q")?.trim();
  if (!q || q.length < 3) {
    return NextResponse.json({ error: "Escribe una dirección más concreta" }, { status: 400 });
  }

  const query = /madrid/i.test(q) ? q : `${q}, Madrid`;
  const params = new URLSearchParams({
    q: query,
    format: "jsonv2",
    addressdetails: "1",
    limit: "1",
    countrycodes: "es",
    bounded: "1",
    viewbox: "-3.90,40.65,-3.50,40.31",
  });

  const res = await fetch(`https://nominatim.openstreetmap.org/search?${params}`, {
    headers: {
      "Accept-Language": "es",
      "User-Agent": "HomesMadrid/1.0 (https://homes.local)",
    },
  });

  if (!res.ok) {
    return NextResponse.json({ error: "No se pudo buscar esa dirección" }, { status: 502 });
  }

  const items = (await res.json()) as NominatimResult[];
  const first = items[0];
  const lat = Number(first?.lat);
  const lng = Number(first?.lon);
  if (!first || !Number.isFinite(lat) || !Number.isFinite(lng) || !isInMadrid(lat, lng)) {
    return NextResponse.json(
      { error: "No hemos encontrado esa dirección dentro de Madrid capital" },
      { status: 404 },
    );
  }

  return NextResponse.json({
    lat,
    lng,
    label: readableLabel(first, q),
    rawLabel: first.display_name ?? q,
  });
}
