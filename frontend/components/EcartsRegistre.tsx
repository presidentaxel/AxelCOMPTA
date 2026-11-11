"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { ErreurAuthChauffeur, lireRegistreOfficiel, trancherEcartRegistre } from "@/lib/auth-chauffeur";
import { phrasePourChauffeur } from "@/lib/langage-chauffeur";
import { ecartsOrdonnes, peutRetenirRegistre, questionEcart, type RegistreVue } from "@/lib/registre";

/** AXE-849 : le registre officiel ne dit pas la même chose que vous. Le
 * chauffeur garde sa déclaration ou retient celle du registre ; tant qu'il
 * ne l'a pas fait, la clôture et la liasse attendent. Rien ne s'affiche
 * sans écart. */
export function EcartsRegistre({ dossierId }: { dossierId: string }) {
  const [registre, setRegistre] = useState<RegistreVue | null>(null);
  const [enCours, setEnCours] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    lireRegistreOfficiel(dossierId)
      .then((lu) => {
        if (actif) setRegistre(lu);
      })
      .catch(() => {
        // Écran secondaire : la clôture dira elle-même ce qui bloque.
      });
    return () => {
      actif = false;
    };
  }, [dossierId]);

  if (!registre || registre.ecarts.length === 0) return null;

  async function trancher(champ: string, retenue: "declaree" | "officielle") {
    setEnCours(champ);
    setErreur(null);
    try {
      await trancherEcartRegistre(dossierId, champ, retenue);
      setRegistre((avant) => avant && { ...avant, ecarts: avant.ecarts.filter((e) => e.champ !== champ) });
    } catch (exception) {
      const message =
        exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
          ? exception.message
          : "Votre choix n'a pas pu être enregistré.";
      setErreur(phrasePourChauffeur(message));
    } finally {
      setEnCours(null);
    }
  }

  return (
    <section aria-labelledby="titre-registre" className="mt-4 rounded-md border border-warning-border bg-warning-subtle p-3">
      <h2 id="titre-registre" className="text-sm font-medium text-ink">
        Le registre officiel dit autre chose
      </h2>
      <p className="mt-1 text-sm text-subtle">Votre bilan ne peut pas être préparé avant votre choix.</p>
      <ul className="mt-3 space-y-4">
        {ecartsOrdonnes(registre.ecarts).map((ecart) => (
          <li key={ecart.champ}>
            <p className="text-sm font-medium text-ink">{questionEcart(ecart.champ)}</p>
            {ecart.champ !== "etat" && (
              <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 text-sm">
                <dt className="text-subtle">Vous</dt>
                <dd className="text-ink">{ecart.declare}</dd>
                <dt className="text-subtle">Registre</dt>
                <dd className="text-ink">{ecart.officiel}</dd>
              </dl>
            )}
            <div className="mt-2 flex flex-col gap-2">
              <Button
                type="button"
                variant="secondary"
                className="h-11 w-full"
                disabled={enCours !== null}
                onClick={() => trancher(ecart.champ, "declaree")}
              >
                {ecart.champ === "etat" ? "Ma société est toujours active" : "Ma déclaration est juste"}
              </Button>
              {peutRetenirRegistre(ecart.champ) && (
                <Button
                  type="button"
                  className="h-11 w-full"
                  disabled={enCours !== null}
                  onClick={() => trancher(ecart.champ, "officielle")}
                >
                  Le registre a raison
                </Button>
              )}
            </div>
            {ecart.champ === "etat" && (
              <p className="mt-2 text-xs text-subtle">Si elle est bien cessée, prévenez votre gestionnaire.</p>
            )}
          </li>
        ))}
      </ul>
      {erreur && <p className="mt-2 text-xs text-danger">{erreur}</p>}
    </section>
  );
}
