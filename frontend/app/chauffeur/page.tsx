"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { obtenirSession } from "@/lib/auth-chauffeur";

/** `/chauffeur` seul n'est pas une page : on ouvre le dossier, ou la connexion. */
export default function ChauffeurIndexPage() {
  const router = useRouter();

  useEffect(() => {
    const session = obtenirSession();
    router.replace(session ? `/chauffeur/${session.dossierId}` : "/chauffeur/login");
  }, [router]);

  return <p className="text-sm text-subtle">Redirection…</p>;
}
