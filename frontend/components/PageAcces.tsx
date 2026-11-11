import type { ReactNode } from "react";

import { Marque } from "@/components/Marque";
import { cn } from "cn";

/** Cadre commun des pages d'accès publiques (connexion, double
 * authentification, lien, désinscription) : fond crème, la marque en haut,
 * une colonne centrée de 440 px. Sur grand écran la page reste sobre : on
 * descend un peu le contenu au lieu d'inventer un panneau décoratif.
 *
 * Le chauffeur a son propre habillage (`app/chauffeur/layout.tsx`, qui porte
 * déjà la marque) : ce cadre n'y sert pas. */
export function PageAcces({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-canvas-app">
      <header className="px-6 pt-8 sm:px-10">
        <Marque />
      </header>
      <main className="mx-auto w-full max-w-[488px] flex-1 px-6 pb-16 pt-12 sm:pt-[12vh]">
        {children}
      </main>
    </div>
  );
}

/** Titre de page d'accès : 28 px, ou 40 px dès qu'il y a la place pour
 * l'écran de connexion (`grand`). */
export function TitreAcces({
  id,
  grand = false,
  children,
}: {
  id?: string;
  grand?: boolean;
  children: ReactNode;
}) {
  return (
    <h1
      id={id}
      className={cn(
        "text-balance text-[28px] font-semibold leading-[1.21] tracking-[-0.02em] text-ink",
        grand && "sm:text-[40px] sm:leading-[1.1]",
      )}
    >
      {children}
    </h1>
  );
}
