"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { delierRollee, lireLienRollee } from "@/lib/auth-gestionnaire";
import { formatDate } from "@/lib/format";
import { effetDelier, type FicheRollee } from "@/lib/liens-rollee";

/** AXE-911 : comment l'entreprise est reliée à Rollee, et le retirer si
 * c'est faux. L'ancien lien reste à l'historique ; ses versements sont
 * contre-passés, jamais supprimés. */
export function LienRollee({
  dossierId,
  ecriture,
  relecture,
  onChange,
}: {
  dossierId: string;
  ecriture: boolean;
  relecture: number;
  onChange: () => void;
}) {
  const [fiche, setFiche] = useState<FicheRollee | null>(null);
  const [essai, setEssai] = useState(0);
  const [confirmer, setConfirmer] = useState(false);
  const [motif, setMotif] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    lireLienRollee(dossierId)
      .then((lue) => {
        if (actif) setFiche(lue);
      })
      .catch(() => {
        // Non lue : rien d'affiché plutôt qu'un faux « non relié ».
      });
    return () => {
      actif = false;
    };
  }, [dossierId, essai, relecture]);

  const relire = useCallback(() => setEssai((n) => n + 1), []);

  async function delier() {
    setMessage(null);
    try {
      const n = await delierRollee(dossierId, motif);
      setMessage(n === 0 ? "Lien retiré." : `Lien retiré, ${n} versement(s) contre-passé(s).`);
      setConfirmer(false);
      setMotif("");
      relire();
      onChange();
    } catch (exception) {
      setMessage(exception instanceof ApiError ? exception.message : "Le lien n'a pas été retiré.");
    }
  }

  if (!fiche) return null;
  return (
    <div className="mt-2 text-sm text-subtle">
      <p>
        {fiche.lien
          ? `Rollee : ${fiche.lien.comment}, le ${formatDate(fiche.lien.relie_le.slice(0, 10))}.`
          : "Rollee : aucun compte relié."}
      </p>
      {fiche.lien && ecriture && !confirmer && (
        <Button type="button" variant="ghost" size="sm" onClick={() => setConfirmer(true)}>
          Retirer ce lien
        </Button>
      )}
      {confirmer && (
        <div className="mt-2 space-y-2">
          <p className="text-ink">{effetDelier(fiche.versements_a_contrepasser)}</p>
          <label className="block">
            Pourquoi ?
            <Input value={motif} onChange={(e) => setMotif(e.target.value)} />
          </label>
          <div className="flex gap-2">
            <Button type="button" size="sm" disabled={!motif.trim()} onClick={() => void delier()}>
              Retirer le lien
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setConfirmer(false)}>
              Annuler
            </Button>
          </div>
        </div>
      )}
      {message && <p className="mt-1 text-xs">{message}</p>}
      {fiche.historique.length > 0 && (
        <ul className="mt-2 text-xs">
          {fiche.historique.map((r) => (
            <li key={r.retire_le}>
              Ancien lien ({r.comment}) retiré le {formatDate(r.retire_le.slice(0, 10))} par{" "}
              {r.retire_par} : {r.motif}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
