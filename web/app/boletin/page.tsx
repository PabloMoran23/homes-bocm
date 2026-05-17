import type { Metadata } from "next";
import { BoletinAreaApp } from "@/components/BoletinAreaApp";

export const metadata: Metadata = {
  title: "Boletín de tu área",
  description:
    "Introduce tu dirección y consulta licencias y expedientes de planeamiento recientes en un radio a tu alrededor.",
};

export default function BoletinPage() {
  return <BoletinAreaApp />;
}
