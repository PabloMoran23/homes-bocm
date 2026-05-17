import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ProjectDetailView } from "@/components/ProjectDetailView";
import { loadProjectById } from "@/lib/load-project";
import { projectHeadline } from "@/lib/project-display";

type PageProps = {
  params: Promise<{ id: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  const project = await loadProjectById(id);
  if (!project) {
    return { title: "Proyecto no encontrado" };
  }
  const title = projectHeadline(project);
  return {
    title: title.length > 72 ? `${title.slice(0, 69)}…` : title,
    description: project.resumen?.slice(0, 160) || undefined,
  };
}

export default async function ProyectoPage({ params }: PageProps) {
  const { id } = await params;
  const project = await loadProjectById(id);
  if (!project) notFound();

  return <ProjectDetailView project={project} />;
}
