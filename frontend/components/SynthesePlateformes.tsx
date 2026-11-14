"use client";

import { useEffect, useState } from "react";

import { LogoPlateforme } from "@/components/LogoPlateforme";
import {
  lireSynthesePlateformes,
  type ComptePlateformeSynthese,
  type SynthesePlateformes as Synthese,
} from "@/lib/auth-gestionnaire";
import { formatDate } from "@/lib/format";
import { etatPlateforme, resumePlateformes } from "@/lib/plateformes";

const RANG_ETAT: Record<ComptePlateformeSynthese["etat"], number> = {
  a_reconnecter: 0,
  en_cours: 1,
  connecte: 2,
};

function groupesDe(comptes: ComptePlateformeSynthese[]) {
  const ordre: { cle: string; titre: string; comptes: ComptePlateformeSynthese[] }[] = [];
  for (const compte of comptes) {
    const cle = compte.rollee_user_id || "";
    const connu = ordre.find((groupe) => groupe.cle === cle);
    if (connu) {
      connu.comptes.push(compte);
    } else {
      ordre.push({ cle, titre: compte.compte_rollee || "", comptes: [compte] });
    }
  }
  return ordre;
}

function joindre(noms: string[]): string {
  if (noms.length <= 1) return noms[0] ?? "";
  return `${noms.slice(0, -1).join(", ")} et ${noms[noms.length - 1]}`;
}

/** AXE-819, doc 19 : le gestionnaire voit chaque plateforme et celles à
 * reconnecter, jamais un montant. */
export function SynthesePlateformes({
  dossierId,
  relecture = 0,
}: {
  dossierId: string;
  relecture?: number;
}) {
  const [synthese, setSynthese] = useState<Synthese | null>(null);
  useEffect(() => {
    let actif = true;
    lireSynthesePlateformes(dossierId)
      .then((lue) => {
        if (actif) setSynthese(lue);
      })
      .catch(() => {
        // Non lue : rien d'affiché plutôt qu'un faux « aucune ».
      });
    return () => {
      actif = false;
    };
  }, [dossierId, relecture]);
  if (!synthese) return null;

  const comptes = [...(synthese.comptes ?? [])].sort(
    (a, b) => RANG_ETAT[a.etat] - RANG_ETAT[b.etat],
  );
  const noms = synthese.noms ?? [];
  const deja = new Set(comptes.map((compte) => compte.nom));
  const sansCompte = noms.filter((nom) => !deja.has(nom));
  const aReconnecter = comptes.filter((compte) => compte.etat === "a_reconnecter");
  const liste = comptes.length > 0 || sansCompte.length > 0;
  const vide = synthese.reliees === 0 && synthese.attendues === 0 && synthese.a_reconnecter === 0;
  const versements = synthese.versements_a_verifier ?? 0;

  return (
    <div className="mt-2">
      {aReconnecter.length > 0 && (
        <p className="rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-sm text-danger">
          {aReconnecter.length === 1
            ? `${aReconnecter[0].nom} est à reconnecter. Ses revenus n'arrivent plus.`
            : `${joindre(aReconnecter.map((compte) => compte.nom))} sont à reconnecter. Leurs revenus n'arrivent plus.`}
        </p>
      )}
      {liste && (
        <div className="mt-2 space-y-3">
          {groupesDe(comptes).map((groupe) => (
            <div key={groupe.cle || groupe.titre || "plateformes"}>
              {groupe.titre && (
                <p className="px-1 text-xs font-medium text-subtle">{groupe.titre}</p>
              )}
              <ul className="space-y-1" aria-label={groupe.titre || "Plateformes Rollee"}>
                {groupe.comptes.map((compte, index) => (
                  <li
                    key={`${groupe.cle}-${compte.nom}-${index}`}
                    className={`flex min-w-0 items-center gap-2 rounded-md px-1 py-1 ${
                      compte.etat === "a_reconnecter" ? "bg-danger-subtle" : ""
                    }`}
                  >
                    <span className="min-w-0 flex-1">
                      <LogoPlateforme nom={compte.nom} />
                    </span>
                    <span
                      className={`shrink-0 text-sm leading-none ${
                        compte.etat === "a_reconnecter" ? "font-medium text-danger" : "text-subtle"
                      }`}
                    >
                      {etatPlateforme(compte, formatDate)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {sansCompte.length > 0 && (
            <ul className="space-y-1">
              {sansCompte.map((nom) => (
                <li key={nom} className="flex h-8 items-center px-1">
                  <LogoPlateforme nom={nom} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {synthese.manquantes.length > 0 && (
        <p className="mt-2 text-sm text-subtle">
          Pas encore reliées : {synthese.manquantes.join(", ")}.
        </p>
      )}
      {versements > 0 && (
        <p className="mt-2 text-sm text-subtle">
          {versements} {versements > 1 ? "versements" : "versement"} à vérifier.
        </p>
      )}
      {!liste && !(vide && noms.length > 0) && (
        <p className="mt-2 text-sm text-subtle">{resumePlateformes(synthese)}</p>
      )}
    </div>
  );
}
