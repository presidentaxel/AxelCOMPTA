"use client";

import { useCallback, useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import {
  lirePlateformesChauffeur,
  ouvrirSessionRolleeChauffeur,
  type PlateformesChauffeur as Donnees,
} from "@/lib/auth-chauffeur";
import { formatDate } from "@/lib/format";
import { etatPlateforme } from "@/lib/plateformes";

import { VersementsPlateformes } from "./VersementsPlateformes";

type EtatBloc =
  | { statut: "en_cours" }
  | { statut: "erreur"; message: string }
  | { statut: "pret"; donnees: Donnees };

/** AXE-819 : le chauffeur relie Uber, Bolt… dans Rollee Connect. Rollee lit
 * ses revenus et ses versements (pas ses courses ni ses positions), pour que
 * le chiffre d'affaires et la TVA soient justes. Ses identifiants restent
 * chez Rollee. */
export function PlateformesChauffeur({ dossierId }: { dossierId: string }) {
  const [etat, setEtat] = useState<EtatBloc>({ statut: "en_cours" });
  const [ouverture, setOuverture] = useState<string | null>(null);

  const charger = useCallback(() => {
    lirePlateformesChauffeur(dossierId)
      .then((donnees) => setEtat({ statut: "pret", donnees }))
      .catch(() => setEtat({ statut: "erreur", message: "Vos plateformes n'ont pas pu être lues." }));
  }, [dossierId]);

  useEffect(() => {
    // Premier chargement, puis relecture au retour de Rollee Connect (onglet revenu au premier plan).
    charger();
    const auRetour = () => {
      if (document.visibilityState === "visible") charger();
    };
    document.addEventListener("visibilitychange", auRetour);
    return () => document.removeEventListener("visibilitychange", auRetour);
  }, [charger]);

  async function relier() {
    setOuverture(null);
    try {
      const { lien } = await ouvrirSessionRolleeChauffeur(dossierId);
      window.open(lien, "_blank", "noopener");
    } catch (exception) {
      setOuverture(exception instanceof Error ? exception.message : "Le lien n'a pas pu être ouvert.");
    }
  }

  return (
    <section className="mb-8" aria-labelledby="titre-plateformes">
      <h2 id="titre-plateformes" className="text-base font-semibold text-ink">
        Mes plateformes
      </h2>
      <p className="mt-1 text-sm text-subtle">
        Reliez Uber, Bolt… : Rollee lit vos revenus et vos versements (pas vos courses), pour que
        votre chiffre d&apos;affaires et votre TVA soient justes. Vos identifiants restent chez Rollee.
      </p>
      {etat.statut === "en_cours" && (
        <Etat type="chargement" className="mt-3">
          <Squelette className="h-10 w-full" />
        </Etat>
      )}
      {etat.statut === "erreur" && (
        <Etat type="erreur" message={etat.message} onReessayer={charger} className="mt-3" />
      )}
      {etat.statut === "pret" && (
        <>
          {etat.donnees.comptes.length > 0 && (
            <ul className="mt-3 space-y-1">
              {etat.donnees.comptes.map((compte) => (
                <li key={compte.nom} className="text-sm text-ink">
                  {compte.nom} :{" "}
                  <span className={compte.etat === "a_reconnecter" ? "text-danger" : "text-subtle"}>
                    {etatPlateforme(compte, formatDate)}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {etat.donnees.manquantes.length > 0 && (
            <p className="mt-2 text-sm text-subtle">
              À relier : {etat.donnees.manquantes.join(", ")}.
            </p>
          )}
          {etat.donnees.erreur && <p className="mt-2 text-sm text-subtle">{etat.donnees.erreur}</p>}
          <Button type="button" variant="secondary" size="sm" className="mt-3" onClick={relier}>
            {etat.donnees.comptes.some((c) => c.etat === "a_reconnecter")
              ? "Reconnecter mes plateformes"
              : "Relier mes plateformes"}
          </Button>
          {ouverture && <p className="mt-2 text-sm text-danger">{ouverture}</p>}
          <VersementsPlateformes dossierId={dossierId} />
        </>
      )}
    </section>
  );
}
