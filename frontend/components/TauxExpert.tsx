"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { poserTauxExpert } from "@/lib/auth-gestionnaire";
import { formatMontant } from "@/lib/format";

const TAUX = [
  { value: "20", label: "20 %" },
  { value: "10", label: "10 %" },
  { value: "5.5", label: "5,5 %" },
  { value: "2.1", label: "2,1 %" },
  { value: "0", label: "0 %" },
];

const ORIGINE: Record<string, string> = {
  table: "proposé",
  appris: "retenu pour ce libellé",
  specifique: "retenu pour cette ligne",
};

/** Le taux proposé, et les deux portées : cette ligne, ou le libellé. */
export function TauxExpert({
  dossierId,
  ecritureId,
  libelle,
  taux,
  tvaCts,
  origine,
  onRetenu,
}: {
  dossierId: string;
  ecritureId: string;
  libelle: string;
  taux: string | null;
  tvaCts: number | null;
  origine: string | null;
  onRetenu: (taux: string) => void;
}) {
  const [brouillon, setBrouillon] = useState<string | null>(null);
  const choisi = brouillon ?? taux ?? "";
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const affiche = TAUX.find((option) => option.value === (taux ?? ""))?.label;

  async function retenir(portee: "specifique" | "global") {
    if (!choisi) return;
    setEnCours(true);
    setErreur(null);
    try {
      await poserTauxExpert({
        dossierId,
        ecritureId,
        libelle,
        taux: choisi,
        portee,
      });
      setBrouillon(null);
      onRetenu(choisi);
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Le taux n'a pas été retenu.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <span className="text-sm text-ink">
        {affiche ? `TVA ${affiche}` : "TVA non proposée"}
        {tvaCts !== null && affiche ? ` · ${formatMontant(tvaCts)}` : ""}
        {origine && ORIGINE[origine] ? ` · ${ORIGINE[origine]}` : ""}
      </span>
      <Select
        aria-label={`Taux de TVA pour ${libelle}`}
        value={choisi}
        onValueChange={setBrouillon}
        placeholder="Taux"
        options={TAUX}
        className="w-28"
      />
      <Button type="button" size="sm" variant="secondary" disabled={!choisi || enCours} onClick={() => void retenir("specifique")}>
        Cette ligne
      </Button>
      <Button type="button" size="sm" variant="ghost" disabled={!choisi || enCours} onClick={() => void retenir("global")}>
        Toutes les lignes semblables
      </Button>
      {erreur && <span className="text-sm text-danger">{erreur}</span>}
    </div>
  );
}
