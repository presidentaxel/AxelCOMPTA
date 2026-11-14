"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { delierRollee, lireLienRollee } from "@/lib/auth-gestionnaire";
import { formatDate } from "@/lib/format";
import { effetDelier, type FicheRollee } from "@/lib/liens-rollee";

/** Trace de qui a relié ou retiré un compte Rollee. Hors de la liste des
 * plateformes : là, on veut seulement savoir de quel compte Rollee vient Bolt. */
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
  const [cible, setCible] = useState<string | null>(null);
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

  async function delier(rolleeUserId: string) {
    setMessage(null);
    try {
      const n = await delierRollee(dossierId, motif, rolleeUserId);
      setMessage(n === 0 ? "Lien retiré." : `Lien retiré, ${n} versement(s) contre-passé(s).`);
      setCible(null);
      setMotif("");
      relire();
      onChange();
    } catch (exception) {
      setMessage(exception instanceof ApiError ? exception.message : "Le lien n'a pas été retiré.");
    }
  }

  if (!fiche) return null;
  const liens = fiche.liens ?? (fiche.lien ? [fiche.lien] : []);
  if (liens.length === 0 && fiche.historique.length === 0) return null;
  return (
    <section className="mt-5 border-t border-border pt-4 text-sm text-subtle">
      <h3 className="text-sm font-medium text-ink">Journal</h3>
      {liens.length > 0 && (
        <ul className="mt-2 space-y-2">
          {liens.map((lien) => (
            <li key={lien.rollee_user_id}>
              <p>
                {formatDate(lien.relie_le.slice(0, 10))} — {lien.comment}.
              </p>
              {ecriture && cible !== lien.rollee_user_id && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setCible(lien.rollee_user_id);
                    setMotif("");
                    setMessage(null);
                  }}
                >
                  Retirer ce lien
                </Button>
              )}
              {cible === lien.rollee_user_id && (
                <div className="mt-2 space-y-2">
                  <p className="text-ink">
                    {effetDelier(lien.versements_a_contrepasser ?? fiche.versements_a_contrepasser)}
                  </p>
                  <label className="block">
                    Pourquoi ?
                    <Input value={motif} onChange={(e) => setMotif(e.target.value)} />
                  </label>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      size="sm"
                      disabled={!motif.trim()}
                      onClick={() => void delier(lien.rollee_user_id)}
                    >
                      Retirer le lien
                    </Button>
                    <Button type="button" variant="ghost" size="sm" onClick={() => setCible(null)}>
                      Annuler
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
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
    </section>
  );
}
