"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { FileText, List, UserRound } from "lucide-react";

import { Cloche } from "@/components/Cloche";
import { GardeCodeCompteDeTest } from "@/components/GardeCodeCompteDeTest";
import { Marque } from "@/components/Marque";
import { IndicateurGlissant } from "@/components/ui/indicateur-glissant";
import { EVENEMENT_ACTIVITE, relireActivite } from "@/lib/activite-url";
import { obtenirSession, type SessionChauffeur } from "@/lib/auth-chauffeur";
import { PAGE_CHOIX_DOSSIER } from "@/lib/compte-de-test";
import { clavierOuvert, insetClavier } from "@/lib/clavier-viewport";

/** Pages d'entrée : pas de navigation, même si une session traîne encore
 * dans le navigateur. */
const PAGES_PUBLIQUES = new Set(["/chauffeur/login", "/chauffeur/accepter-invitation"]);

/** Colonne unique de 600 px (DESIGN.md § Espace chauffeur), centrée sur un
 * grand écran. En-tête, bandeau, contenu et barre du bas partagent la même
 * largeur pour que leurs bords restent alignés. */
const COLONNE = "mx-auto w-full max-w-[600px]";

/** Habillage chauffeur — webapp téléphone, lisible aussi sur un grand
 * écran (colonne centrée). Même calme que le portefeuille gestionnaire :
 * marque, écran en colonne, une barre du bas. Aucun élément du design
 * interne : ni barre de navigation horizontale, ni tableau.
 *
 * La coque est fixe et suit le visual viewport (`--vvh`, `--vv-offset`),
 * pas `100vh` : la barre du bas reste au bord visible, et se retire quand
 * le clavier couvre ce bord (iOS Safari, Chrome Android, Samsung Internet). */
export default function ChauffeurLayout({ children }: { children: React.ReactNode }) {
  const chemin = usePathname();
  const [session, setSession] = useState<SessionChauffeur | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSession(obtenirSession());
  }, [chemin]);

  useEffect(() => {
    const vv = window.visualViewport;
    let plein = window.innerHeight;

    const publier = () => {
      const hauteur = vv?.height ?? window.innerHeight;
      const decalage = vv?.offsetTop ?? 0;
      if (window.innerHeight > plein) plein = window.innerHeight;
      const inset = insetClavier(plein, hauteur, decalage);
      const racine = document.documentElement;
      racine.style.setProperty("--vvh", `${Math.round(hauteur)}px`);
      racine.style.setProperty("--vv-offset", `${Math.round(decalage)}px`);
      racine.style.setProperty("--clavier-inset", `${inset}px`);
      racine.toggleAttribute("data-clavier", clavierOuvert(inset));
    };

    const recalerChamp = () => {
      publier();
      const actif = document.activeElement;
      if (actif instanceof HTMLElement && actif.matches("input, textarea, select")) {
        window.setTimeout(() => actif.scrollIntoView({ block: "nearest" }), 50);
      }
    };

    const surOrientation = () => {
      plein = window.innerHeight;
      publier();
    };

    publier();
    vv?.addEventListener("resize", recalerChamp);
    vv?.addEventListener("scroll", publier);
    window.addEventListener("orientationchange", surOrientation);
    return () => {
      vv?.removeEventListener("resize", recalerChamp);
      vv?.removeEventListener("scroll", publier);
      window.removeEventListener("orientationchange", surOrientation);
      const racine = document.documentElement;
      racine.style.removeProperty("--vvh");
      racine.style.removeProperty("--vv-offset");
      racine.style.removeProperty("--clavier-inset");
      racine.removeAttribute("data-clavier");
    };
  }, []);

  // Le compte de test sans dossier choisi n'a ni cloche ni barre (AXE-822).
  const espace =
    session !== null && !PAGES_PUBLIQUES.has(chemin) && chemin !== PAGE_CHOIX_DOSSIER &&
    session.dossierId !== "";

  return (
    <div className="chauffeur bg-canvas-app">
      <GardeCodeCompteDeTest />
      <header className="shrink-0 border-b border-border bg-canvas pt-[env(safe-area-inset-top)]">
        <div className={`${COLONNE} flex h-14 items-center px-4`}>
          <Marque />
          {espace && session && <Cloche dossierId={session.dossierId} chemin={chemin} />}
        </div>
      </header>
      {session?.lecteurTest && !PAGES_PUBLIQUES.has(chemin) && (
        <BandeauCompteDeTest session={session} chemin={chemin} />
      )}
      <main
        className={`chauffeur-main ${COLONNE} min-h-0 flex-1 overflow-x-clip overflow-y-auto px-4 py-6 ${
          espace ? "" : "sans-barre"
        }`}
      >
        {children}
      </main>
      {espace && session && <Barre dossierId={session.dossierId} chemin={chemin} />}
    </div>
  );
}

/** AXE-822 : rappel permanent que l'on regarde le dossier d'un autre, sans
 * pouvoir rien changer, et le chemin pour en changer. */
function BandeauCompteDeTest({ session, chemin }: { session: SessionChauffeur; chemin: string }) {
  const dossier = session.dossierNom || session.dossierId;
  return (
    <div role="status" className="shrink-0 border-b border-warning/40 bg-pending-subtle">
      <p className={`${COLONNE} flex items-center justify-between gap-3 px-4 py-1 text-sm text-ink`}>
        <span className="min-w-0 truncate">
          Mode test, lecture seule{dossier ? ` — ${dossier}` : ""}
        </span>
        {chemin !== PAGE_CHOIX_DOSSIER && (
          <Link
            href={PAGE_CHOIX_DOSSIER}
            className="inline-flex min-h-11 shrink-0 items-center font-semibold text-signal underline decoration-2 underline-offset-[3px] hover:text-signal-deep"
          >
            Changer de dossier
          </Link>
        )}
      </p>
    </div>
  );
}

function Barre({ dossierId, chemin }: { dossierId: string; chemin: string }) {
  const activite = `/chauffeur/${dossierId}`;
  const exercice = `/chauffeur/${dossierId}/exercice`;
  const resultat = `/chauffeur/${dossierId}/resultat`;
  const compte = "/chauffeur/compte";
  const [requeteActivite, setRequeteActivite] = useState("");

  useEffect(() => {
    const lire = () => setRequeteActivite(relireActivite(dossierId));
    lire();
    window.addEventListener(EVENEMENT_ACTIVITE, lire);
    return () => window.removeEventListener(EVENEMENT_ACTIVITE, lire);
  }, [dossierId]);

  const hrefActivite = requeteActivite ? `${activite}?${requeteActivite}` : activite;
  const liens = [
    { href: hrefActivite, libelle: "Activité", Icone: List, actif: chemin === activite },
    {
      href: exercice,
      libelle: "Exercice",
      Icone: FileText,
      actif: chemin === exercice || chemin === resultat,
    },
    { href: compte, libelle: "Compte", Icone: UserRound, actif: chemin === compte },
  ];

  return (
    <nav aria-label="Navigation" className="barre-chauffeur shrink-0">
      <div className={`${COLONNE} border-t border-border bg-canvas pb-[env(safe-area-inset-bottom)]`}>
        {/* Le filet de 2 px de l'entrée active glisse d'une entrée à l'autre
            (la barre reste montée). `relative` l'ancre ; `-top-px` et
            `bottom-auto!` le posent sur le filet haut de la barre, alors que
            l'indicateur est pensé pour se poser sous une rangée. */}
        <div className="relative grid grid-cols-3">
          {liens.map(({ href, libelle, Icone, actif }) => (
            <Link
              key={href}
              href={href}
              aria-current={actif ? "page" : undefined}
              className={`flex h-14 flex-col items-center justify-center gap-0.5 text-xs outline-none transition-colors duration-150 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-signal ${
                actif ? "font-semibold text-ink" : "font-medium text-subtle"
              }`}
            >
              <Icone className="h-5 w-5" aria-hidden />
              {libelle}
            </Link>
          ))}
          <IndicateurGlissant selecteur='[aria-current="page"]' className="-top-px bottom-auto!" />
        </div>
      </div>
    </nav>
  );
}
