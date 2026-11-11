"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  importerDossiers,
  suivreImport,
  telechargerModeleImport,
  verifierImport,
  type RapportImport,
} from "@/lib/auth-gestionnaire";
import type { Synchronisation } from "@/lib/types";
import { useDroitGestionnaire } from "@/lib/use-droit";

/** AXE-809 : créer les entreprises d'un portefeuille sans Digifactory depuis
 * un fichier CSV. Rapport ligne par ligne d'abord ; les lignes en erreur ne
 * sont pas créées. Le dirigeant confirme ensuite sa configuration. */
export default function ImportDossiersPage() {
  const droit = useDroitGestionnaire();
  const [fichier, setFichier] = useState<File | null>(null);
  const [sirene, setSirene] = useState(false);
  const [rapport, setRapport] = useState<RapportImport | null>(null);
  const [suivi, setSuivi] = useState<Synchronisation | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  const enCours = suivi?.statut === "en_attente" || suivi?.statut === "en_cours";
  useEffect(() => {
    if (!enCours) return;
    const minuterie = window.setInterval(() => {
      suivreImport().then(setSuivi).catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(minuterie);
  }, [enCours]);

  async function agir(action: () => Promise<RapportImport>) {
    setEnvoi(true);
    setErreur(null);
    try {
      const resultat = await action();
      setRapport(resultat);
      if (resultat.creation) setSuivi(resultat.creation);
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
    } finally {
      setEnvoi(false);
    }
  }

  async function modele() {
    const blob = await telechargerModeleImport();
    const lien = document.createElement("a");
    lien.href = URL.createObjectURL(blob);
    lien.download = "modele-entreprises.csv";
    lien.click();
    URL.revokeObjectURL(lien.href);
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Importer des entreprises</h1>
      <p className="mt-2 text-sm text-subtle">
        Une ligne par société, au format du modèle (CSV, séparateur « ; »). Chaque ligne est
        vérifiée avant toute création : SIREN, combinaison forme × impôt × TVA, dates d&apos;exercice.
        Le dirigeant confirme ensuite sa configuration à sa première connexion.
      </p>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button type="button" variant="secondary" size="sm" onClick={() => void modele()}>
          Télécharger le modèle
        </Button>
        <input
          type="file"
          accept=".csv,text/csv"
          aria-label="Fichier des entreprises"
          onChange={(e) => {
            setFichier(e.target.files?.[0] ?? null);
            setRapport(null);
          }}
          className="text-sm"
        />
        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" checked={sirene} onChange={(e) => setSirene(e.target.checked)} />
          Comparer avec Sirene (plus lent)
        </label>
        <Button
          type="button"
          size="sm"
          disabled={!fichier || envoi}
          onClick={() => fichier && void agir(() => verifierImport(fichier, sirene))}
        >
          Vérifier
        </Button>
      </div>
      {erreur && <p className="mt-4 text-sm text-danger">{erreur}</p>}
      {rapport && (
        <section className="mt-8" aria-label="Rapport de vérification">
          <p className="text-sm text-ink">
            {rapport.a_creer} entreprise{rapport.a_creer > 1 ? "s" : ""} prête{rapport.a_creer > 1 ? "s" : ""} à
            créer, {rapport.en_erreur} ligne{rapport.en_erreur > 1 ? "s" : ""} en erreur.
          </p>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="h-9 border-b border-border bg-canvas-app text-left text-xs font-semibold uppercase tracking-wide text-subtle">
                <th className="px-2">Ligne</th>
                <th className="px-2">Entreprise</th>
                <th className="px-2">Vérification</th>
              </tr>
            </thead>
            <tbody>
              {rapport.lignes.map((ligne) => (
                <tr key={ligne.numero} className="border-b border-hairline align-top">
                  <td className="px-2 py-2 tabular-nums text-subtle">{ligne.numero}</td>
                  <td className="px-2 py-2 text-ink">{ligne.nom ?? "—"}</td>
                  <td className="px-2 py-2">
                    {ligne.erreurs.length === 0 ? (
                      <span className="text-validated">À créer</span>
                    ) : (
                      ligne.erreurs.map((e) => (
                        <span key={e} className="block text-danger">{e}</span>
                      ))
                    )}
                    {ligne.avertissements.map((a) => (
                      <span key={a} className="block text-subtle">{a}</span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {droit.admin && rapport.a_creer > 0 && !suivi && (
            <Button
              type="button"
              className="mt-4"
              disabled={!fichier || envoi}
              onClick={() => fichier && void agir(() => importerDossiers(fichier))}
            >
              Créer les {rapport.a_creer} entreprises
            </Button>
          )}
        </section>
      )}
      {suivi && (
        <p role="status" className="mt-4 text-sm text-ink">
          {enCours ? "Création en cours…" : (suivi.resultat ?? suivi.erreur ?? "")}{" "}
          {!enCours && <Link href="/" className="text-signal underline">Voir les entreprises</Link>}
        </p>
      )}
    </div>
  );
}
