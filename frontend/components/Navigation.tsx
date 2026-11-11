"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Dialog, Popover } from "radix-ui";

import { Marque } from "@/components/Marque";
import { Input } from "@/components/ui/input";
import {
  deconnecterGestionnaire,
  lireNomPortefeuille,
  obtenirSessionGestionnaire,
  renommerPortefeuille,
} from "@/lib/auth-gestionnaire";
import { ENTREES_GESTIONNAIRE, entreeActive, initiales } from "@/lib/navigation";
import { useDroitGestionnaire } from "@/lib/use-droit";

/** Barre de navigation du gestionnaire (DESIGN.md § Navigation et
 * § Application shell) : 64px, fond `canvas`, filet bas `border`. La marque et
 * les sept entrées à gauche, la zone de compte à droite.
 *
 * Responsive, en classes `lg:` seulement : à partir de 1024px les entrées sont
 * dans la barre ; en dessous (≤ 1023px) elles passent dans le tiroir du bouton
 * « Menu », et la zone de compte reste visible.
 *
 * `alertes` : href des entrées « qui demandent une action » (point `signal`
 * à droite du libellé). Vide tant qu'aucun écran ne fournit l'information. */
export function Navigation({ alertes = {} }: { alertes?: Partial<Record<string, boolean>> }) {
  const chemin = usePathname();
  const [tiroirOuvert, setTiroirOuvert] = useState(false);

  return (
    <header className="flex h-16 shrink-0 items-stretch gap-8 border-b border-border bg-canvas px-10">
      <div className="flex items-center">
        <Marque />
      </div>

      <nav aria-label="Gestionnaire" className="-mb-px hidden items-stretch gap-6 lg:flex">
        {ENTREES_GESTIONNAIRE.map(({ href, libelle }) => {
          const actif = entreeActive(chemin, href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={actif ? "page" : undefined}
              className={`flex items-center gap-1.5 border-b-2 text-sm whitespace-nowrap outline-none transition-colors duration-150 focus-visible:shadow-focus-detache ${
                actif
                  ? "border-ink font-semibold text-ink"
                  : "border-transparent font-medium text-muted hover:text-ink"
              }`}
            >
              {libelle}
              {alertes[href] && <PointAlerte />}
            </Link>
          );
        })}
      </nav>

      <div className="ml-auto flex items-center gap-2">
        <Dialog.Root open={tiroirOuvert} onOpenChange={setTiroirOuvert}>
          <Dialog.Trigger asChild>
            <button
              type="button"
              className="flex h-11 min-w-11 items-center justify-center rounded-md px-3 text-sm font-semibold text-ink outline-none transition-colors duration-150 hover:bg-surface-soft focus-visible:shadow-focus-detache lg:hidden"
            >
              Menu
            </button>
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/50 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 motion-reduce:animate-none lg:hidden" />
            <Dialog.Content
              aria-describedby={undefined}
              className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r border-border bg-canvas px-6 py-6 text-ink shadow-overlay outline-none data-[state=open]:animate-in data-[state=open]:slide-in-from-left data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left motion-reduce:animate-none lg:hidden"
            >
              <Dialog.Title className="sr-only">Navigation</Dialog.Title>
              <div className="pb-6">
                <Marque />
              </div>
              <nav aria-label="Gestionnaire" className="flex flex-col gap-1">
                {ENTREES_GESTIONNAIRE.map(({ href, libelle }) => {
                  const actif = entreeActive(chemin, href);
                  return (
                    <Dialog.Close asChild key={href}>
                      <Link
                        href={href}
                        aria-current={actif ? "page" : undefined}
                        className={`flex min-h-11 items-center gap-2 rounded-md border-l-2 px-3 text-sm outline-none transition-colors duration-150 focus-visible:shadow-focus-detache ${
                          actif
                            ? "border-ink font-semibold text-ink"
                            : "border-transparent font-medium text-muted hover:bg-surface-soft hover:text-ink"
                        }`}
                      >
                        {libelle}
                        {alertes[href] && <PointAlerte />}
                      </Link>
                    </Dialog.Close>
                  );
                })}
              </nav>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>

        <CompteGestionnaire chemin={chemin} />
      </div>
    </header>
  );
}

/** Le point ne distingue jamais seul (DESIGN.md § Accessibilité) : le libellé
 * de l'entrée et ce texte, lu par les lecteurs d'écran, disent qu'une action
 * est attendue. */
function PointAlerte() {
  return (
    <>
      <span aria-hidden className="size-[7px] shrink-0 rounded-full bg-signal" />
      <span className="sr-only">, une action est attendue</span>
    </>
  );
}

/** Zone de compte : l'avatar ouvre un menu avec le nom de l'organisation
 * (modifiable par un admin), l'e-mail, le lien Compte et la déconnexion. À
 * partir de 1280px le nom de l'organisation reste lisible à côté de l'avatar. */
function CompteGestionnaire({ chemin }: { chemin: string }) {
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

  return (
    <div className="flex items-center gap-3">
      <span className="hidden max-w-48 truncate text-sm text-muted xl:block">{nom}</span>
      <Popover.Root open={ouvert} onOpenChange={setOuvert}>
        <Popover.Trigger asChild>
          <button
            type="button"
            aria-label="Compte"
            className="flex size-8 shrink-0 items-center justify-center rounded-full bg-ink text-xs font-semibold text-on-primary outline-none transition-colors duration-150 hover:bg-primary-bright focus-visible:shadow-focus-detache"
          >
            {initiales(email)}
          </button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content
            align="end"
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
    </div>
  );
}
