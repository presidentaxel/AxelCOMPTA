"use client";

// doc 06 §5 point 5 : le chauffeur sait qu'une charge de l'exercice n'est
// pas encore dans la banque. Il donne le montant. Le moteur ne décide pas
// à sa place quand provisionner.
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  enregistrerProvisionsCloture,
  lireProvisionsCloture,
} from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";
import type { ProvisionClotureVue } from "@/lib/types";

function eurosEnCentimes(saisie: string): number | null {
  const texte = saisie.trim().replace(/\s/g, "").replace(",", ".");
  const morceaux = /^(\d+)(?:\.(\d{1,2}))?$/.exec(texte);
  if (morceaux === null) {
    return null;
  }
  const cents = (morceaux[2] ?? "").padEnd(2, "0");
  return Number(morceaux[1]) * 100 + Number(cents);
}

export function ProvisionsCloture({
  dossierId,
  onChange,
}: {
  dossierId: string;
  onChange: () => void;
}) {
  const [lignes, setLignes] = useState<ProvisionClotureVue[]>([]);
  const [nature, setNature] = useState<"cca" | "fnp">("fnp");
  const [compte, setCompte] = useState("");
  const [montant, setMontant] = useState("");
  const [libelle, setLibelle] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  useEffect(() => {
    lireProvisionsCloture(dossierId)
      .then(setLignes)
      .catch(() => setLignes([]));
  }, [dossierId]);

  async function envoyer(suivantes: ProvisionClotureVue[]): Promise<boolean> {
    setEnCours(true);
    setErreur(null);
    try {
      const enregistrees = await enregistrerProvisionsCloture(dossierId, suivantes);
      setLignes(enregistrees);
      onChange();
      return true;
    } catch (exception) {
      setErreur(
        exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
          ? exception.message
          : "Échec de l'enregistrement.",
      );
      return false;
    } finally {
      setEnCours(false);
    }
  }

  async function ajouter() {
    const centimes = eurosEnCentimes(montant);
    if (centimes === null || centimes <= 0 || compte.trim() === "" || libelle.trim() === "") {
      setErreur("Indiquez un compte de charge, un montant et un libellé.");
      return;
    }
    const ok = await envoyer([
      ...lignes,
      { nature, compte_charge: compte.trim(), centimes, libelle: libelle.trim() },
    ]);
    if (!ok) {
      return;
    }
    setCompte("");
    setMontant("");
    setLibelle("");
  }

  return (
    <div className="mt-4 rounded-md border border-border bg-canvas p-3">
      <p className="text-sm text-ink">Une charge de cet exercice n&apos;est pas encore passée ?</p>
      <p className="mt-1 text-sm text-subtle">
        Donnez votre estimation. Elle sera prise dans la clôture. Rien n&apos;est deviné.
      </p>
      {lignes.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-ink">
          {lignes.map((ligne) => (
            <li key={`${ligne.nature}-${ligne.compte_charge}-${ligne.libelle}`} className="flex justify-between gap-3">
              <span>
                {ligne.nature === "cca" ? "Payée d'avance" : "Facture pas encore reçue"} —{" "}
                {ligne.libelle} ({ligne.compte_charge})
              </span>
              <span>{formatMontant(ligne.centimes)}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <select
          className="h-8 rounded-sm border border-border bg-canvas px-2 text-sm"
          value={nature}
          onChange={(evenement) => setNature(evenement.target.value === "cca" ? "cca" : "fnp")}
        >
          <option value="fnp">Facture pas encore reçue</option>
          <option value="cca">Déjà payée, pour plus tard</option>
        </select>
        <input
          className="h-8 w-24 rounded-sm border border-border px-2 text-sm"
          inputMode="numeric"
          placeholder="Compte"
          aria-label="Compte de charge"
          value={compte}
          onChange={(evenement) => setCompte(evenement.target.value)}
        />
        <input
          className="h-8 w-24 rounded-sm border border-border px-2 text-sm"
          inputMode="decimal"
          placeholder="Montant"
          aria-label="Montant"
          value={montant}
          onChange={(evenement) => setMontant(evenement.target.value)}
        />
        <input
          className="h-8 min-w-40 flex-1 rounded-sm border border-border px-2 text-sm"
          placeholder="Libellé"
          aria-label="Libellé"
          value={libelle}
          onChange={(evenement) => setLibelle(evenement.target.value)}
        />
        <Button type="button" variant="secondary" disabled={enCours} onClick={ajouter}>
          Ajouter
        </Button>
      </div>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </div>
  );
}
