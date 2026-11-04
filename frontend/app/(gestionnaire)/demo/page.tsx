"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  ErreurAuthGestionnaire,
  listerPartiesDemo,
  reinitialiserDemo,
  type PartieDemo,
} from "@/lib/auth-gestionnaire";

const JAMAIS_TOUCHE = [
  "Le grand livre : les écritures restent telles quelles.",
  "Le journal d'audit, qui garde aussi la trace de la remise à neuf.",
  "Les comptes de connexion et l'équipe avec ses rôles.",
];

/** Menu Démo : remettre à neuf, à la carte, les données du portefeuille de
 * démo. Rien n'est coché d'avance, rien ne part sans confirmation. */
export default function DemoPage() {
  const router = useRouter();
  const [parties, setParties] = useState<PartieDemo[] | null>(null);
  const [cochees, setCochees] = useState<string[]>([]);
  const [confirmer, setConfirmer] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    listerPartiesDemo()
      .then(setParties)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) router.replace("/connexion");
        else setErreur(exception instanceof Error ? exception.message : "Menu indisponible.");
      });
  }, [router]);

  function basculer(cle: string) {
    setConfirmer(false);
    setMessage(null);
    setCochees((actuel) => (actuel.includes(cle) ? actuel.filter((c) => c !== cle) : [...actuel, cle]));
  }

  async function remettreANeuf() {
    setEnCours(true);
    setErreur(null);
    try {
      const dossiers = await reinitialiserDemo(cochees);
      const libelles = (parties ?? []).filter((p) => cochees.includes(p.cle)).map((p) => p.libelle);
      setMessage(`Remis à neuf sur ${dossiers.length} entreprises : ${libelles.join(", ")}.`);
      setCochees([]);
    } catch (exception) {
      if (exception instanceof ErreurAuthGestionnaire) router.replace("/connexion");
      else setErreur(exception instanceof Error ? exception.message : "Échec de la remise à neuf.");
    } finally {
      setEnCours(false);
      setConfirmer(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Démo</h1>
      <p className="mt-2 text-sm text-subtle">
        Remettre les données du portefeuille de démo dans leur état de départ, avant ou après une
        présentation. Cochez seulement ce que vous voulez effacer.
      </p>

      {parties && (
        <ul className="mt-8">
          {parties.map((partie) => (
            <li key={partie.cle} className="border-b border-hairline">
              <label className="flex cursor-pointer items-start gap-3 py-4">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={cochees.includes(partie.cle)}
                  onChange={() => basculer(partie.cle)}
                />
                <span>
                  <span className="block text-sm font-medium text-ink">{partie.libelle}</span>
                  <span className="mt-1 block text-sm text-subtle">{partie.detail}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-6 rounded-lg bg-surface-soft px-4 py-3">
        <p className="text-sm font-medium text-ink">Jamais touché</p>
        <ul className="mt-1 space-y-0.5 text-sm text-subtle">
          {JAMAIS_TOUCHE.map((ligne) => (
            <li key={ligne}>{ligne}</li>
          ))}
        </ul>
      </div>

      <div className="mt-6 flex items-center gap-3">
        {confirmer ? (
          <>
            <Button variant="danger" onClick={remettreANeuf} disabled={enCours}>
              {enCours ? "Remise à neuf…" : "Confirmer, c'est définitif"}
            </Button>
            <Button variant="ghost" onClick={() => setConfirmer(false)} disabled={enCours}>
              Annuler
            </Button>
          </>
        ) : (
          <Button onClick={() => setConfirmer(true)} disabled={cochees.length === 0}>
            Remettre à neuf ({cochees.length})
          </Button>
        )}
      </div>

      {message && <p className="mt-4 text-sm text-success">{message}</p>}
      {erreur && <p className="mt-4 text-sm text-danger">{erreur}</p>}
    </div>
  );
}
