"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Dialog, Popover } from "radix-ui";

import { LiensJuridiques } from "@/components/LiensJuridiques";
import { Marque } from "@/components/Marque";
import { IndicateurGlissant } from "@/components/ui/indicateur-glissant";
import { Input } from "@/components/ui/input";
import {
  deconnecterGestionnaire,
  lireNomPortefeuille,
  obtenirSessionGestionnaire,
  renommerPortefeuille,
} from "@/lib/auth-gestionnaire";
import {
  ENTREES_GESTIONNAIRE,
  cheminAffiche,
  entreeActive,
  initiales,
  type EntreeEnAttente,
} from "@/lib/navigation";
import { useDroitGestionnaire } from "@/lib/use-droit";

/** Barre latérale du gestionnaire (DESIGN.md § Navigation et § Application
 * shell) : 256px, fond `canvas`, filet droit `border`, collée à la hauteur de
 * l'écran. La marque en haut, les sept entrées, la zone de compte en bas.
 *
 * Responsive, en classes `lg:` seulement : à partir de 1024px la barre
 * latérale est fixe ; en dessous (≤ 1023px) elle devient une barre de 56px avec
 * la marque, le bouton « Menu » (qui ouvre les mêmes entrées dans un tiroir) et
 * l'avatar. Le filet de l'entrée active est un indicateur glissant (180 ms) à
 * gauche de la colonne, pas une bordure par entrée.
 *
 * `alertes` : href des entrées « qui demandent une action » (point `signal`
 * à droite du libellé). Vide tant qu'aucun écran ne fournit l'information. */
export function Navigation({ alertes = {} }: { alertes?: Partial<Record<string, boolean>> }) {
  const cheminReel = usePathname();
  const [attente, setAttente] = useState<EntreeEnAttente | null>(null);
  // Le filet part au clic, pas à l'arrivée de la page (voir `cheminAffiche`).
  const chemin = cheminAffiche(cheminReel, attente);
  const [tiroirOuvert, setTiroirOuvert] = useState(false);

  const entrees = (
    <ListeEntrees
      chemin={chemin}
      alertes={alertes}
      auClic={(href) => setAttente({ href, depuis: cheminReel })}
    />
  );

  return (
    <>
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col border-r border-border bg-canvas lg:flex">
        <div className="flex h-14 shrink-0 items-center px-4">
          <Marque />
        </div>
        <nav aria-label="Gestionnaire" className="flex-1 overflow-y-auto px-2 py-1">
          {entrees}
        </nav>
        <div className="shrink-0 border-t border-border p-2">
          <CompteGestionnaire chemin={chemin} variante="pied" />
          <LiensJuridiques className="mt-1.5 px-2" />
        </div>
      </aside>

      <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border bg-canvas px-4 lg:hidden">
        <Marque />
        <div className="flex items-center gap-2">
          <Dialog.Root open={tiroirOuvert} onOpenChange={setTiroirOuvert}>
            <Dialog.Trigger asChild>
              <button
                type="button"
                className="flex h-11 min-w-11 items-center justify-center rounded-md px-3 text-sm font-semibold text-ink outline-none transition-colors duration-150 hover:bg-surface-soft focus-visible:shadow-focus-detache"
              >
                Menu
              </button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/50 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 motion-reduce:animate-none lg:hidden" />
              <Dialog.Content
                aria-describedby={undefined}
                className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r border-border bg-canvas py-6 text-ink shadow-overlay outline-none data-[state=open]:animate-in data-[state=open]:slide-in-from-left data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left motion-reduce:animate-none lg:hidden"
              >
                <Dialog.Title className="sr-only">Navigation</Dialog.Title>
                <div className="px-6 pb-6">
                  <Marque />
                </div>
                <nav aria-label="Gestionnaire" className="flex-1 overflow-y-auto px-3">
                  <ListeEntrees
                    chemin={chemin}
                    alertes={alertes}
                    auClic={(href) => {
                      setAttente({ href, depuis: cheminReel });
                      setTiroirOuvert(false);
                    }}
                  />
                </nav>
                <LiensJuridiques className="mt-4 px-6" />
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
          <CompteGestionnaire chemin={chemin} variante="compacte" />
        </div>
      </header>
    </>
  );
}

/** Les sept entrées en colonne, avec le filet qui glisse de l'une à l'autre
 * (la barre reste montée d'une page à l'autre) au lieu de réapparaître. */
function ListeEntrees({
  chemin,
  alertes,
  auClic,
}: {
  chemin: string;
  alertes: Partial<Record<string, boolean>>;
  auClic: (href: string) => void;
}) {
  return (
    <div className="relative flex flex-col gap-0.5">
      {ENTREES_GESTIONNAIRE.map(({ href, libelle }) => {
        const actif = entreeActive(chemin, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={actif ? "page" : undefined}
            onClick={() => auClic(href)}
            className={`relative z-10 flex min-h-11 items-center lg:min-h-9 gap-2 rounded-md px-3 text-[13px] whitespace-nowrap outline-none transition-colors duration-150 focus-visible:shadow-focus-detache ${
              actif ? "font-semibold text-ink" : "font-medium text-muted hover:text-ink"
            }`}
          >
            {libelle}
            {alertes[href] && <PointAlerte />}
          </Link>
        );
      })}
      <IndicateurGlissant selecteur='[aria-current="page"]' axe="vertical" forme="bulle" />
    </div>
  );
}

/** Le point ne distingue jamais seul (DESIGN.md § Accessibilité) : le libellé
 * de l'entrée et ce texte, lu par les lecteurs d'écran, disent qu'une action
 * est attendue. */
function PointAlerte() {
  return (
    <>
      <span aria-hidden className="ml-auto size-[7px] shrink-0 rounded-full bg-signal" />
      <span className="sr-only">, une action est attendue</span>
    </>
  );
}

/** Zone de compte : l'avatar (avec, dans la barre latérale, le nom de
 * l'organisation et l'e-mail) ouvre un menu avec le nom de l'organisation
 * (modifiable par un admin), l'e-mail, le lien Compte et la déconnexion. */
function CompteGestionnaire({
  chemin,
  variante,
}: {
  chemin: string;
  variante: "pied" | "compacte";
}) {
  const droit = useDroitGestionnaire();
  const router = useRouter();
  const [ouvert, setOuvert] = useState(false);
  const [email, setEmail] = useState("");
  const [nom, setNom] = useState("Organisation");
  const [erreurNom, setErreurNom] = useState<string | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEmail(obtenirSessionGestionnaire()?.email ?? "");
    lireNomPortefeuille()
      .then((valeur) => {
        if (valeur) setNom(valeur);
      })
      .catch(() => undefined);
  }, []);

  async function enregistrerNom() {
    if (!droit.admin) return;
    const propre = nom.trim();
    if (!propre) {
      const relu = await lireNomPortefeuille().catch(() => "");
      if (relu) setNom(relu);
      return;
    }
    setErreurNom(null);
    try {
      setNom(await renommerPortefeuille(propre));
    } catch (exception) {
      setErreurNom(exception instanceof Error ? exception.message : "Impossible d'enregistrer le nom.");
      const relu = await lireNomPortefeuille().catch(() => "");
      if (relu) setNom(relu);
    }
  }

  function seDeconnecter() {
    deconnecterGestionnaire();
    router.push("/connexion");
  }

  const surCompte = entreeActive(chemin, "/compte");
  const avatar = (
    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-ink text-[11px] font-semibold text-on-primary">
      {initiales(email)}
    </span>
  );

  return (
    <Popover.Root open={ouvert} onOpenChange={setOuvert}>
      <Popover.Trigger asChild>
        {variante === "pied" ? (
          <button
            type="button"
            aria-label="Compte"
            className="flex min-h-10 w-full items-center gap-2.5 rounded-md px-2 text-left outline-none transition-colors duration-150 hover:bg-surface-soft focus-visible:shadow-focus-detache"
          >
            {avatar}
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-semibold text-ink">{nom}</span>
              <span className="block truncate text-xs text-subtle">{email}</span>
            </span>
          </button>
        ) : (
          <button
            type="button"
            aria-label="Compte"
            className="flex size-11 items-center justify-center rounded-md outline-none transition-colors duration-150 hover:bg-surface-soft focus-visible:shadow-focus-detache"
          >
            {avatar}
          </button>
        )}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side={variante === "pied" ? "top" : "bottom"}
          align={variante === "pied" ? "start" : "end"}
          sideOffset={8}
          // Le focus entre dans le menu, pas dans le champ du nom : sinon
          // ouvrir puis refermer le menu déclencherait un enregistrement.
          onOpenAutoFocus={(evenement) => {
            evenement.preventDefault();
            (evenement.currentTarget as HTMLElement).focus();
          }}
          className="z-50 w-72 max-w-[calc(100vw-2rem)] rounded-md border border-border bg-canvas p-3 text-ink shadow-md outline-none"
        >
          <div className="px-1 pb-3">
            <span className="block text-xs text-subtle">Organisation</span>
            <Input
              value={nom}
              onChange={(evenement) => setNom(evenement.target.value)}
              onBlur={() => void enregistrerNom()}
              onKeyDown={(evenement) => {
                if (evenement.key !== "Enter") return;
                evenement.preventDefault();
                void enregistrerNom();
              }}
              readOnly={!droit.admin}
              aria-label="Nom de l'organisation"
              className="mt-1 truncate font-semibold read-only:cursor-default read-only:border-transparent read-only:bg-transparent read-only:px-0 read-only:shadow-none"
            />
            {erreurNom && <span className="mt-1 block text-xs text-danger">{erreurNom}</span>}
            <p className="mt-2 truncate text-xs text-subtle">{email}</p>
          </div>
          <div className="border-t border-border pt-2">
            <Link
              href="/compte"
              aria-current={surCompte ? "page" : undefined}
              onClick={() => setOuvert(false)}
              className={`flex min-h-9 items-center rounded-md px-2 text-sm outline-none hover:bg-surface-soft hover:text-ink focus-visible:shadow-focus ${
                surCompte ? "font-semibold text-ink" : "text-subtle"
              }`}
            >
              Compte
            </Link>
            <button
              type="button"
              onClick={seDeconnecter}
              className="mt-1 flex min-h-9 w-full items-center rounded-md px-2 text-left text-sm text-subtle outline-none hover:bg-surface-soft hover:text-ink focus-visible:shadow-focus"
            >
              Se déconnecter
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
