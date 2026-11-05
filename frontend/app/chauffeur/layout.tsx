"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { FileText, List, UserRound } from "lucide-react";

import { Cloche } from "@/components/Cloche";
import { Marque } from "@/components/Marque";
import { obtenirSession, type SessionChauffeur } from "@/lib/auth-chauffeur";

/** Pages d'entrée : pas de navigation, même si une session traîne encore
 * dans le navigateur. */
const PAGES_PUBLIQUES = new Set(["/chauffeur/login", "/chauffeur/accepter-invitation"]);

/** Habillage chauffeur — webapp téléphone, lisible aussi sur un grand
 * écran (colonne centrée). Même calme que le portefeuille gestionnaire :
 * marque, liste, une barre du bas. Pas de Sidebar. */
export default function ChauffeurLayout({ children }: { children: React.ReactNode }) {
  const chemin = usePathname();
  const [session, setSession] = useState<SessionChauffeur | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSession(obtenirSession());
  }, [chemin]);

  const espace = session !== null && !PAGES_PUBLIQUES.has(chemin);

  return (
    <div className="chauffeur-ecran min-h-dvh bg-canvas-app">
      <header className="sticky top-0 z-10 border-b border-border bg-canvas pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex h-14 max-w-md items-center px-4">
          <Marque />
          {espace && session && <Cloche dossierId={session.dossierId} chemin={chemin} />}
        </div>
      </header>
      <main
        className={`mx-auto min-w-0 max-w-md overflow-x-clip px-4 py-6 ${
          espace ? "pb-[calc(6rem+env(safe-area-inset-bottom))]" : ""
        }`}
      >
        {children}
      </main>
      {espace && session && <Barre dossierId={session.dossierId} chemin={chemin} />}
    </div>
  );
}

function Barre({ dossierId, chemin }: { dossierId: string; chemin: string }) {
  const activite = `/chauffeur/${dossierId}`;
  const exercice = `/chauffeur/${dossierId}/exercice`;
  const compte = "/chauffeur/compte";
  const resultat = `/chauffeur/${dossierId}/resultat`;
  const liens = [
    {
      href: activite,
      libelle: "Activité",
      Icone: List,
      actif: chemin === activite,
    },
    {
      href: exercice,
      libelle: "Exercice",
      Icone: FileText,
      actif: chemin === exercice || chemin === resultat,
    },
    { href: compte, libelle: "Compte", Icone: UserRound, actif: chemin === compte },
  ];

  return (
    <nav className="fixed bottom-0 left-1/2 z-10 w-full max-w-md -translate-x-1/2 border-t border-border bg-canvas">
      <div className="grid grid-cols-3 pb-[env(safe-area-inset-bottom)]">
        {liens.map(({ href, libelle, Icone, actif }) => (
          <Link
            key={href}
            href={href}
            className={`flex h-14 flex-col items-center justify-center gap-0.5 text-xs ${
              actif ? "font-semibold text-ink" : "text-subtle"
            }`}
          >
            <Icone className="h-5 w-5" aria-hidden />
            {libelle}
          </Link>
        ))}
      </div>
    </nav>
  );
}
