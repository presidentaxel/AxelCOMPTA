"use client";

// doc 06 §5 point 5 : le chauffeur sait qu'une charge de l'exercice n'est
// pas encore dans la banque. Il donne le montant. Le moteur ne décide pas
// à sa place quand provisionner.
//
// La lecture et la liste vide sont deux états. Tant que la lecture n'a pas
// réussi, `lignes` reste null : aucun PUT ne part, sinon `[...lignes, nouvelle]`
// remplacerait les provisions déjà saisies par la seule ligne ajoutée.
import { useCallback, useEffect, useRef, useState } from "react";

import { EchecLecture, messageEchecLecture } from "@/components/EchecLecture";
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
  const [lignes, setLignes] = useState<ProvisionClotureVue[] | null>(null);
  const [echecLecture, setEchecLecture] = useState<string | null>(null);
  const [enCoursLecture, setEnCoursLecture] = useState(false);
  const [nature, setNature] = useState<"cca" | "fnp">("fnp");
  const [compte, setCompte] = useState<string>(CHARGES_CLOTURE[0].compte);
  const [montant, setMontant] = useState("");
  const [libelle, setLibelle] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [suivi, setSuivi] = useState(dossierId);
  const ticket = useRef(0);

  if (suivi !== dossierId) {
    setSuivi(dossierId);
    setLignes(null);
    setEchecLecture(null);
    setErreur(null);
  }

  const relire = useCallback(() => {
    const courant = ++ticket.current;
    lireProvisionsCloture(dossierId)
      .then((lues) => {
        if (ticket.current !== courant) return;
        setLignes(lues);
        setEchecLecture(null);
        setEnCoursLecture(false);
      })
      .catch((exception: unknown) => {
        if (ticket.current !== courant) return;
        setLignes(null);
        setEchecLecture(
          messageEchecLecture(exception, "Impossible de charger ce qui est déjà saisi."),
        );
        setEnCoursLecture(false);
      });
  }, [dossierId]);

  useEffect(() => {
    relire();
  }, [relire]);

  function reessayer() {
    setEnCoursLecture(true);
    relire();
  }

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
    if (lignes === null) return;
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

  async function retirer(index: number) {
    if (lignes === null) return;
    await envoyer(lignes.filter((_, position) => position !== index));
  }

  return (
    <section
      aria-labelledby="provisions-titre"
      className="mt-8 rounded-md border border-border bg-canvas p-3"
    >
      <p id="provisions-titre" className="text-sm text-ink">
        Une charge de cet exercice n&apos;est pas encore passée ?
      </p>
      <p className="mt-1 text-sm text-subtle">
        Donnez votre estimation. Elle sera prise dans la clôture. Rien n&apos;est deviné.
      </p>
      {echecLecture && (
        <EchecLecture message={echecLecture} onReessayer={reessayer} enCours={enCoursLecture} />
      )}
      {lignes !== null && lignes.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-ink">
          {lignes.map((ligne, index) => (
            <li
              key={`${index}-${ligne.nature}-${ligne.compte_charge}-${ligne.libelle}`}
              className="flex items-center justify-between gap-3"
            >
              <span className="min-w-0">
                <span className="block">
                  {NOM_NATURE[ligne.nature]} — {ligne.libelle}
                </span>
                <span className="tabular-nums">{formatMontant(ligne.centimes)}</span>
              </span>
              <button
                type="button"
                className="inline-flex h-11 shrink-0 items-center justify-center rounded-md px-3 text-sm font-semibold text-danger outline-none focus-visible:shadow-[0_0_0_3px_rgba(37,99,235,0.45)] disabled:opacity-50"
                disabled={enCours}
                aria-label={`Retirer ${ligne.libelle}`}
                onClick={() => retirer(index)}
              >
                Retirer
              </button>
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
        <Button
          type="button"
          variant="secondary"
          className="h-11 w-full"
          disabled={enCours || lignes === null}
          onClick={ajouter}
        >
          Ajouter
        </Button>
      </div>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </section>
  );
}
