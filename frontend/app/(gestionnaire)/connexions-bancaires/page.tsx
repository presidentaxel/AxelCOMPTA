"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  type ConnexionDossier,
  type ConnexionsBancaires,
  ErreurAuthGestionnaire,
  lireConnexionsBancaires,
  type ModeRelance,
  reglerRelanceDossier,
  reglerRelancePortefeuille,
} from "@/lib/auth-gestionnaire";
import { formatDate } from "@/lib/format";

const STATUTS: Record<ConnexionDossier["statut"], string> = {
  expire: "Expirée",
  a_renouveler: "À renouveler",
  jamais_connecte: "Jamais connectée",
  actif: "Active",
};

const SANTES: Partial<Record<ConnexionDossier["sante"], string>> = {
  auth_requise: "La banque demande de confirmer",
  sans_acces: "Accès aux données coupé",
  en_pause: "En pause",
};

const MODES: { mode: ModeRelance; titre: string; detail: string }[] = [
  {
    mode: "auto",
    titre: "Relance automatique",
    detail:
      "AxeLCompta prévient l'entreprise dans son application : deux semaines avant, une semaine avant, à l'expiration, puis tous les 3 jours. Aucun SMS ni e-mail ne part.",
  },
  {
    mode: "manuel",
    titre: "Relance manuelle",
    detail:
      "Rien n'est envoyé. Vous suivez cette page et vous contactez l'entreprise vous-même. L'envoi par SMS ou e-mail n'est pas branché.",
  },
];

/** doc 14 §2.2 et §2.3 : l'état des connexions bancaires, écran de premier
 * rang, et le mode de relance du portefeuille ou d'un dossier. */
export default function ConnexionsBancairesPage() {
  const router = useRouter();
  const [donnees, setDonnees] = useState<ConnexionsBancaires | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  const charger = useCallback(() => {
    lireConnexionsBancaires()
      .then(setDonnees)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) router.replace("/connexion");
        else setErreur("Impossible de charger les connexions bancaires.");
      });
  }, [router]);

  useEffect(() => {
    charger();
  }, [charger]);

  async function regler(action: () => Promise<void>) {
    setEnCours(true);
    setErreur(null);
    try {
      await action();
      charger();
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Réglage refusé.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Connexions bancaires</h1>
      <p className="mt-2 text-sm text-subtle">
        Sans connexion valide, les opérations d&apos;une entreprise n&apos;arrivent plus. L&apos;envoi
        d&apos;une relance par SMS ou e-mail n&apos;est pas branché.
      </p>
      {erreur && <p className="mt-4 text-sm text-danger">{erreur}</p>}
      {donnees && (
        <>
          <dl className="mt-8 flex flex-wrap gap-x-12 gap-y-4">
            <Compteur libelle="Expirées" valeur={donnees.compteurs.expire} alerte />
            <Compteur libelle="À confirmer" valeur={donnees.a_reconnecter} alerte />
            <Compteur libelle="À renouveler (14 jours)" valeur={donnees.compteurs.a_renouveler} />
            <Compteur libelle="Actives" valeur={donnees.compteurs.actif} />
            <Compteur libelle="Jamais connectées" valeur={donnees.compteurs.jamais_connecte} />
          </dl>

          <section className="mt-10">
            <h2 className="text-sm font-medium text-ink">Relances des entreprises</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {MODES.map(({ mode, titre, detail }) => {
                const actif = donnees.relance_portefeuille === mode;
                return (
                  <button
                    key={mode}
                    type="button"
                    disabled={enCours || actif}
                    onClick={() => void regler(() => reglerRelancePortefeuille(mode))}
                    aria-pressed={actif}
                    className={`rounded-md border p-4 text-left ${actif ? "border-primary bg-primary-subtle" : "border-border hover:border-ink"}`}
                  >
                    <span className="text-sm font-medium text-ink">{titre}</span>
                    <span className="mt-1 block text-xs text-subtle">{detail}</span>
                  </button>
                );
              })}
            </div>
          </section>

          <table className="mt-10 w-full text-left text-sm">
            <thead className="text-xs text-subtle">
              <tr className="border-b border-hairline">
                <th className="py-2 font-medium">Entreprise</th>
                <th className="py-2 font-medium">Connexion</th>
                <th className="py-2 font-medium">Expire le</th>
                <th className="py-2 font-medium">Dernière mise à jour</th>
                <th className="py-2 font-medium">Relances</th>
              </tr>
            </thead>
            <tbody>
              {donnees.dossiers.map((dossier) => (
                <tr key={dossier.dossier_id} className="border-b border-hairline align-top">
                  <td className="py-3 text-ink">{dossier.nom}</td>
                  <td className="py-3">
                    <Etat dossier={dossier} />
                  </td>
                  <td className="py-3 tabular-nums text-ink">
                    {dossier.expire_le ? formatDate(dossier.expire_le) : "—"}
                    {dossier.jours_restants !== null && dossier.jours_restants >= 0 && (
                      <span className="block text-xs text-subtle">
                        dans {dossier.jours_restants} jour{dossier.jours_restants > 1 ? "s" : ""}
                      </span>
                    )}
                  </td>
                  <td className="py-3 tabular-nums text-subtle">
                    {dossier.dernier_rafraichissement
                      ? formatDate(dossier.dernier_rafraichissement)
                      : "—"}
                  </td>
                  <td className="py-3">
                    {(dossier.statut === "expire" || dossier.statut === "a_renouveler") && (
                      <Link href="/rappels" className="mb-2 block text-sm font-medium text-primary hover:underline">
                        Relancer
                      </Link>
                    )}
                    <select
                      aria-label={`Relances pour ${dossier.nom}`}
                      disabled={enCours}
                      value={dossier.relance_propre ? dossier.relance : "portefeuille"}
                      onChange={(evenement) => {
                        const valeur = evenement.target.value;
                        void regler(() =>
                          reglerRelanceDossier(
                            dossier.dossier_id,
                            valeur === "portefeuille" ? null : (valeur as ModeRelance),
                          ),
                        );
                      }}
                      className="rounded-md border border-border bg-canvas px-2 py-1 text-sm text-ink"
                    >
                      <option value="portefeuille">
                        Comme le portefeuille ({donnees.relance_portefeuille === "auto" ? "automatique" : "manuel"})
                      </option>
                      <option value="auto">Automatique</option>
                      <option value="manuel">Manuel</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function Compteur({ libelle, valeur, alerte = false }: { libelle: string; valeur: number; alerte?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-subtle">{libelle}</dt>
      <dd
        className={`text-[22px] font-bold tabular-nums ${alerte && valeur > 0 ? "text-danger" : "text-ink"}`}
      >
        {valeur}
      </dd>
    </div>
  );
}

function Etat({ dossier }: { dossier: ConnexionDossier }) {
  const probleme = SANTES[dossier.sante];
  const urgent = dossier.statut === "expire" || dossier.sante === "auth_requise";
  return (
    <span className={urgent ? "text-danger" : dossier.statut === "a_renouveler" ? "text-warning" : "text-ink"}>
      {STATUTS[dossier.statut]}
      {probleme && <span className="block text-xs">{probleme}</span>}
    </span>
  );
}
