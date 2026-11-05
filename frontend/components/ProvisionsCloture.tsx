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
import { CHARGES_CLOTURE, NOM_NATURE, phrasePourChauffeur } from "@/lib/langage-chauffeur";
import type { ProvisionClotureVue } from "@/lib/types";

const CHAMP =
  "h-11 w-full rounded-md border border-border bg-canvas px-3 text-base text-ink outline-none placeholder:text-muted focus-visible:border-border-focus focus-visible:shadow-[0_0_0_3px_rgba(37,99,235,0.45)]";

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
  const [compte, setCompte] = useState<string>(CHARGES_CLOTURE[0].compte);
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
        phrasePourChauffeur(
          exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
            ? exception.message
            : "Échec de l'enregistrement.",
        ),
      );
      return false;
    } finally {
      setEnCours(false);
    }
  }

  async function ajouter() {
    const centimes = eurosEnCentimes(montant);
    if (centimes === null || centimes <= 0 || libelle.trim() === "") {
      setErreur("Indiquez de quoi il s'agit, un montant et un libellé.");
      return;
    }
    const ok = await envoyer([
      ...lignes,
      { nature, compte_charge: compte, centimes, libelle: libelle.trim() },
    ]);
    if (!ok) {
      return;
    }
    setCompte(CHARGES_CLOTURE[0].compte);
    setMontant("");
    setLibelle("");
  }

  return (
    <div className="mt-8 rounded-md border border-border bg-canvas p-3">
      <p className="text-sm text-ink">Une charge de cet exercice n&apos;est pas encore passée ?</p>
      <p className="mt-1 text-sm text-subtle">
        Donnez votre estimation. Elle sera prise dans la clôture. Rien n&apos;est deviné.
      </p>
      {lignes.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-ink">
          {lignes.map((ligne) => (
            <li key={`${ligne.nature}-${ligne.compte_charge}-${ligne.libelle}`} className="flex justify-between gap-3">
              <span>
                {NOM_NATURE[ligne.nature]} — {ligne.libelle}
              </span>
              <span>{formatMontant(ligne.centimes)}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-col gap-2">
        <select
          className={CHAMP}
          value={nature}
          onChange={(evenement) => setNature(evenement.target.value === "cca" ? "cca" : "fnp")}
        >
          <option value="fnp">{NOM_NATURE.fnp}</option>
          <option value="cca">{NOM_NATURE.cca}</option>
        </select>
        <select
          className={CHAMP}
          aria-label="De quoi s'agit-il ?"
          value={compte}
          onChange={(evenement) => setCompte(evenement.target.value)}
        >
          {CHARGES_CLOTURE.map((charge) => (
            <option key={charge.compte} value={charge.compte}>
              {charge.libelle}
            </option>
          ))}
        </select>
        <input
          className={CHAMP}
          inputMode="decimal"
          placeholder="Montant"
          aria-label="Montant"
          value={montant}
          onChange={(evenement) => setMontant(evenement.target.value)}
        />
        <input
          className={CHAMP}
          placeholder="Libellé"
          aria-label="Libellé"
          value={libelle}
          onChange={(evenement) => setLibelle(evenement.target.value)}
        />
        <Button type="button" variant="secondary" className="h-11 w-full" disabled={enCours} onClick={ajouter}>
          Ajouter
        </Button>
      </div>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </div>
  );
}
