"use client";

import { Check, LoaderCircle } from "lucide-react";
import { useRef, useState } from "react";

import { ZoneDeTexte } from "@/components/ZoneDeTexte";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { basculerChoix, type ChampImport } from "@/lib/fiches-import";

export type Enregistrer = (champs: Record<string, string>) => Promise<void>;
type Etat = "repos" | "envoi" | "fait";

const TYPES_INPUT: Partial<Record<ChampImport["type"], string>> = {
  date: "date",
  email: "email",
  telephone: "tel",
};

/** AXE-946 : un champ de la fiche qui s'enregistre seul, à la sortie du
 * champ (texte) ou au choix (liste). L'erreur s'affiche dessous, la saisie
 * reste pour être corrigée. */
export function ChampAuto({
  champ,
  modifiable,
  duRegistre,
  enregistrer,
}: {
  champ: ChampImport;
  modifiable: boolean;
  duRegistre: boolean;
  enregistrer: Enregistrer;
}) {
  // `null` : le champ suit la fiche (registre, déductions) ; sinon la saisie
  // en cours, gardée tant que des envois sont en vol (optimistic UI).
  const [brouillon, setBrouillon] = useState<string | null>(null);
  const [etat, setEtat] = useState<Etat>("repos");
  const [erreur, setErreur] = useState<string | null>(null);
  const enVol = useRef(0);
  const valeur = brouillon ?? champ.valeur;
  const id = `champ-${champ.cle}`;

  async function envoyer(nouvelle: string) {
    if (nouvelle.trim() === champ.valeur && enVol.current === 0) {
      setBrouillon(null);
      return;
    }
    enVol.current += 1;
    setEtat("envoi");
    setErreur(null);
    try {
      await enregistrer({ [champ.cle]: nouvelle.trim() });
      setEtat("fait");
      if (enVol.current === 1) setBrouillon((b) => (b === nouvelle ? null : b));
    } catch (exception) {
      setEtat("repos");
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
    } finally {
      enVol.current -= 1;
    }
  }

  return (
    <div className={champ.type === "long" || champ.type === "multi" ? "sm:col-span-2" : undefined}>
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {champ.libelle}
          {champ.obligatoire && !champ.valeur && <span className="ml-1 font-normal text-muted">· attendu</span>}
        </label>
        <EtatChamp etat={etat} duRegistre={duRegistre} />
      </div>
      <div className="mt-1.5">
        <Saisie
          id={id}
          champ={champ}
          valeur={valeur}
          desactive={!modifiable}
          onChange={(v) => {
            setBrouillon(v);
            setEtat("repos");
            if (champ.type === "choix" || champ.type === "multi") void envoyer(v);
          }}
          onBlur={() => void envoyer(valeur)}
        />
      </div>
      {erreur ? (
        <p role="alert" className="mt-1 text-xs text-danger">{erreur}</p>
      ) : (
        champ.aide && <p className="mt-1 text-xs text-muted">{champ.aide}</p>
      )}
    </div>
  );
}

function EtatChamp({ etat, duRegistre }: { etat: Etat; duRegistre: boolean }) {
  if (etat === "envoi") {
    return <LoaderCircle aria-label="Enregistrement" className="size-3.5 animate-spin text-muted" />;
  }
  if (etat === "fait") {
    return (
      <span className="flex items-center gap-1 text-xs text-success">
        <Check className="size-3.5" aria-hidden /> Enregistré
      </span>
    );
  }
  return duRegistre ? <span className="text-xs text-muted">Registre</span> : null;
}

function Saisie({
  id,
  champ,
  valeur,
  desactive,
  onChange,
  onBlur,
}: {
  id: string;
  champ: ChampImport;
  valeur: string;
  desactive: boolean;
  onChange: (valeur: string) => void;
  onBlur: () => void;
}) {
  if (champ.type === "choix") {
    return (
      <Select
        id={id}
        value={valeur}
        disabled={desactive}
        onValueChange={onChange}
        placeholder="Choisir"
        options={champ.choix.map((c) => ({ value: c.cle, label: c.libelle }))}
      />
    );
  }
  if (champ.type === "multi") {
    return (
      <div id={id} className="flex flex-wrap gap-2" role="group" aria-label={champ.libelle}>
        {champ.choix.map((c) => {
          const coche = valeur.split(",").includes(c.cle);
          return (
            <Button
              key={c.cle}
              type="button"
              size="sm"
              variant={coche ? "secondary" : "ghost"}
              aria-pressed={coche}
              disabled={desactive}
              onClick={() => onChange(basculerChoix(valeur, c.cle))}
            >
              {coche && <Check className="size-3.5" aria-hidden />}
              {c.libelle}
            </Button>
          );
        })}
      </div>
    );
  }
  if (champ.type === "long") {
    return (
      <ZoneDeTexte
        id={id}
        rows={3}
        value={valeur}
        disabled={desactive}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
      />
    );
  }
  return (
    <Input
      id={id}
      type={TYPES_INPUT[champ.type] ?? "text"}
      inputMode={champ.type === "montant" || champ.type === "siret" ? "decimal" : undefined}
      placeholder={champ.type === "jour_mois" ? "31/12" : undefined}
      value={valeur}
      disabled={desactive}
      onChange={(e) => onChange(e.target.value)}
      onBlur={onBlur}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
      }}
    />
  );
}
