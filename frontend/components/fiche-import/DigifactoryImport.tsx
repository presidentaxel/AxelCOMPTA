"use client";

import { Check, LoaderCircle, Unplug } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { chercherDigifactoryImport } from "@/lib/auth-gestionnaire";
import type { DigifactoryFiche } from "@/lib/fiches-import";

import type { Enregistrer } from "./ChampAuto";

/** AXE-947 : comme la synchro, la fiche cherche le contact Digifactory de la
 * personne (SIREN, entreprise, nom et prénom). Rien trouvé : la banque n'est
 * pas encore connectée. Relier = garder son numéro sur la fiche. */
export function DigifactoryImport({
  ficheId,
  contactActuel,
  cle,
  modifiable,
  enregistrer,
}: {
  ficheId: string;
  contactActuel: string;
  cle: string; // relance la recherche quand le nom ou le SIREN change
  modifiable: boolean;
  enregistrer: Enregistrer;
}) {
  const [resultat, setResultat] = useState<{ cle: string; vue: DigifactoryFiche } | null>(null);
  const [choisi, setChoisi] = useState(contactActuel);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    chercherDigifactoryImport(ficheId)
      .then((vue) => actif && setResultat({ cle, vue }))
      .catch(() => actif && setResultat({ cle, vue: { lu: false, contacts: [] } }));
    return () => {
      actif = false;
    };
  }, [ficheId, cle]);

  async function relier(contactNr: string) {
    const avant = choisi;
    setChoisi(contactNr); // tout de suite ; l'API confirme
    setErreur(null);
    try {
      await enregistrer({ contact_digifactory: contactNr });
    } catch (exception) {
      setChoisi(avant);
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
    }
  }

  const vue = resultat?.cle === cle ? resultat.vue : null;
  return (
    <div className="space-y-3 rounded-lg border border-border p-4 sm:col-span-2">
      <p className="text-sm font-medium text-ink">Compte Digifactory</p>
      {vue === null ? (
        <p className="flex items-center gap-2 text-sm text-subtle">
          <LoaderCircle className="size-4 animate-spin" aria-hidden /> Recherche dans Digifactory…
        </p>
      ) : !vue.lu ? (
        <p className="text-sm text-subtle">Digifactory n&apos;a pas répondu : saisissez le numéro de contact s&apos;il est connu.</p>
      ) : vue.contacts.length === 0 ? (
        <p className="flex items-center gap-2 text-sm text-ink">
          <Unplug className="size-4 text-subtle" aria-hidden />
          Pas encore connecté à Digifactory : aucun contact à ce nom ni à ce SIREN.
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-md border border-border">
          {vue.contacts.map((c) => {
            const relie = choisi === c.contact_nr;
            return (
              <li key={c.contact_nr} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                <span className="min-w-0">
                  <span className="font-medium text-ink">{c.nom}</span>
                  <span className="ml-2 text-subtle">
                    contact {c.contact_nr} · {c.raison}
                    {c.a_un_dossier && " · déjà un dossier dans Entreprises"}
                  </span>
                </span>
                {modifiable && (
                  <Button size="sm" variant={relie ? "secondary" : "ghost"} onClick={() => !relie && void relier(c.contact_nr)}>
                    {relie && <Check className="size-3.5" aria-hidden />}
                    {relie ? "Relié" : "Relier"}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {erreur && <p role="alert" className="text-sm text-danger">{erreur}</p>}
    </div>
  );
}
