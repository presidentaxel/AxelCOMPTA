"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Squelette } from "@/components/Squelette";
import { obtenirSession } from "@/lib/auth-chauffeur";

/** `/chauffeur` seul mène au dossier ouvert, ou à la connexion. */
export default function ChauffeurIndexPage() {
  const router = useRouter();

  useEffect(() => {
    const session = obtenirSession();
    router.replace(session ? `/chauffeur/${session.dossierId}` : "/chauffeur/login");
  }, [router]);

  return <Squelette className="h-40 w-full" />;
}