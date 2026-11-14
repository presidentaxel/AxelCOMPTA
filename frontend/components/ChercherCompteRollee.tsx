"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { chercherCompteRollee, lierCompteRollee } from "@/lib/auth-gestionnaire";
import { detailFiche, rechercheAssezLongue, type FicheAnnuaireRollee } from "@/lib/liens-rollee";

const ATTENTE_MS = 250;

/** Le gestionnaire cherche le compte Rollee de l'entreprise par son nom,
 * parmi les users déjà lus, et le relie. Un user déjà relié ailleurs se
 * voit, sans pouvoir être choisi. */
export function ChercherCompteRollee({
  dossierId,
  onRelie,
}: {
  dossierId: string;
  onRelie: () => void;
}) {
  const [requete, setRequete] = useState("");
  const [fiches, setFiches] = useState<FicheAnnuaireRollee[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    if (!rechercheAssezLongue(requete)) return;
    let actif = true;
    const minuterie = window.setTimeout(() => {
      chercherCompteRollee(requete)
        .then((trouvees) => {
          if (actif) setFiches(trouvees);
        })
        .catch(() => {
          if (actif) setErreur("La recherche n'a pas abouti.");
        });
    }, ATTENTE_MS);
    return () => {
      actif = false;
      window.clearTimeout(minuterie);
    };
  }, [requete]);

  async function relier(fiche: FicheAnnuaireRollee) {
    setEnvoi(true);
    setErreur(null);
    try {
      await lierCompteRollee(dossierId, fiche.rollee_user_id);
      onRelie();
    } catch (exception) {
      setErreur(exception instanceof ApiError ? exception.message : "Le lien n'a pas été posé.");
    } finally {
      setEnvoi(false);
    }
  }

  const visibles = rechercheAssezLongue(requete) ? fiches : null;
  return (
    <div className="mt-2 space-y-2">
      <label className="block text-ink">
        Chercher son compte Rollee
        <Input
          value={requete}
          onChange={(evenement) => {
            setErreur(null);
            setRequete(evenement.target.value);
          }}
          placeholder="Nom ou prénom du chauffeur"
          aria-label="Chercher un compte Rollee par nom"
        />
      </label>
      {visibles && visibles.length === 0 && (
        <p className="text-xs">
          Aucun compte Rollee à ce nom. S&apos;il vient d&apos;être créé, lancez Synchroniser Rollee.
        </p>
      )}
      {visibles && visibles.length > 0 && (
        <ul className="divide-y divide-hairline" aria-label="Comptes Rollee trouvés">
          {visibles.map((fiche) => (
            <li key={fiche.rollee_user_id} className="flex flex-wrap items-center gap-3 py-2">
              <span className="flex-1">
                <span className="block text-ink">{fiche.nom}</span>
                <span className="block text-xs">
                  {detailFiche(fiche)}
                  {fiche.relie_a ? ` · déjà relié à ${fiche.relie_a}` : ""}
                </span>
              </span>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={envoi || fiche.relie_a !== null}
                onClick={() => void relier(fiche)}
              >
                Relier
              </Button>
            </li>
          ))}
        </ul>
      )}
      {erreur && <p className="text-xs text-danger">{erreur}</p>}
    </div>
  );
}
