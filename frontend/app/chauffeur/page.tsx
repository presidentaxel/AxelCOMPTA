"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { obtenirSession } from "@/lib/auth-chauffeur";
import { cheminDuDossier } from "@/lib/compte-de-test";

/** `/chauffeur` seul n'est pas une page : on ouvre le dossier, ou la connexion. */
export default function ChauffeurIndexPage() {
  const router = useRouter();

  useEffect(() => {
    const session = obtenirSession();
    router.replace(session ? cheminDuDossier(session) : "/chauffeur/login");
  }, [router]);

  return <p className="text-sm text-subtle">Redirection…</p>;
}
