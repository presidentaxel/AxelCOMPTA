"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  declencherRappel,
  ErreurAuthGestionnaire,
  lireConnexionsBancaires,
  lirePortefeuilleSession,
  listerDossiers,
  listerRegles,
  retirerDossier,
  type RegleRappel,
} from "@/lib/auth-gestionnaire";
import {
  libelleBanque,
  libelleCompte,
  libelleImposition,
  libelleRegimeTva,
  libelleTvaRecettes,
} from "@/lib/dossier-libelles";
import { formatDate, formatMontant } from "@/lib/format";
import type { DossierAgregat } from "@/lib/types";

type FiltreCompte = "tous" | "sans_compte" | "invite" | "ouvert";
type FiltreResultat = "tous" | "negatif" | "positif";

export default function PortefeuillePage() {
  const router = useRouter();
  const [dossiers, setDossiers] = useState<DossierAgregat[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [recherche, setRecherche] = useState("");
  const [compte, setCompte] = useState<FiltreCompte>("tous");
  const [resultat, setResultat] = useState<FiltreResultat>("tous");
  const [forme, setForme] = useState("toutes");
  const [tva, setTva] = useState("toutes");
  const [selection, setSelection] = useState<string | null>(null);
  const [regles, setRegles] = useState<RegleRappel[]>([]);
  const [infoRappel, setInfoRappel] = useState<string | null>(null);
  const [confirmerRetrait, setConfirmerRetrait] = useState(false);

  const charger = useCallback(() => {
    listerDossiers()
      .then(setDossiers)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) {
          router.replace("/connexion");
        } else {
          setErreur("Impossible de charger les entreprises.");
        }
      });
  }, [router]);

  useEffect(() => {
    const memo = lirePortefeuilleSession();
    // Lecture de sessionStorage avant le rafraîchissement réseau.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (memo) setDossiers(memo);
    charger();
    listerRegles().then(setRegles).catch(() => setRegles([]));
  }, [charger]);

  const formes = useMemo(
    () => [...new Set((dossiers ?? []).map((dossier) => dossier.forme_juridique))].sort(),
    [dossiers],
  );
  const tvas = useMemo(
    () => [...new Set((dossiers ?? []).map((dossier) => dossier.tva_recettes_regime))].sort(),
    [dossiers],
  );

  const visibles = useMemo(() => {
    const aiguille = recherche.trim().toLowerCase();
    return (dossiers ?? []).filter((dossier) => {
      if (compte === "sans_compte" && dossier.statut_invitation !== null) return false;
      if (compte === "invite" && dossier.statut_invitation !== "invité") return false;
      if (compte === "ouvert" && dossier.statut_invitation !== "actif") return false;
      if (resultat === "negatif" && dossier.resultat_cts >= 0) return false;
      if (resultat === "positif" && dossier.resultat_cts < 0) return false;
      if (forme !== "toutes" && dossier.forme_juridique !== forme) return false;
      if (tva !== "toutes" && dossier.tva_recettes_regime !== tva) return false;
      if (!aiguille) return true;
      return `${dossier.nom} ${dossier.plateformes.join(" ")}`.toLowerCase().includes(aiguille);
    });
  }, [compte, dossiers, forme, recherche, resultat, tva]);

  const totaux = useMemo(() => {
    const liste = dossiers ?? [];
    return {
      nombre: liste.length,
      sansCompte: liste.filter((dossier) => dossier.statut_invitation === null).length,
      resultat: liste.reduce((somme, dossier) => somme + dossier.resultat_cts, 0),
    };
  }, [dossiers]);

  const choisi = dossiers?.find((dossier) => dossier.dossier_id === selection) ?? null;

  return (
    <div className="-m-8 flex min-h-screen">
    <div className="min-w-0 flex-1 p-8">
      <div className="flex items-start justify-between gap-6">
        <h1 className="text-[28px] font-bold tracking-tight text-ink">Entreprises</h1>
        <Link href="/invitations" className="mt-2 text-sm font-medium text-primary hover:underline">
          Invitations
        </Link>
      </div>
      <AlerteConnexions />
      {dossiers && (
        <dl className="mt-8 flex flex-wrap gap-x-12 gap-y-4">
          <Total libelle="Entreprises" valeur={String(totaux.nombre)} />
          <Total libelle="Sans compte" valeur={String(totaux.sansCompte)} />
          <Total libelle="Résultat" valeur={formatMontant(totaux.resultat)} montant={totaux.resultat} />
        </dl>
      )}

      <div className="mt-8 flex items-center gap-2">
        <Input
          value={recherche}
          onChange={(evenement) => setRecherche(evenement.target.value)}
          placeholder="Rechercher une entreprise"
          aria-label="Rechercher une entreprise"
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Bascule
          libelle="Compte"
          valeur={compte}
          options={ORDRE_COMPTE.map((id) => ({ id, libelle: LIBELLES_COMPTE[id] }))}
          onChoisir={setCompte}
        />
        <Bascule
          libelle="Résultat"
          valeur={resultat}
          options={ORDRE_RESULTAT.map((id) => ({ id, libelle: LIBELLES_RESULTAT[id] }))}
          onChoisir={setResultat}
        />
        <Bascule
          libelle="Forme"
          valeur={forme}
          options={["toutes", ...formes].map((id) => ({ id, libelle: id === "toutes" ? "Toutes" : id }))}
          onChoisir={setForme}
        />
        <Bascule
          libelle="TVA"
          valeur={tva}
          options={["toutes", ...tvas].map((id) => ({
            id,
            libelle: id === "toutes" ? "Toutes" : libelleTvaRecettes(id),
          }))}
          onChoisir={setTva}
        />
      </div>

      {erreur && <p className="mt-6 text-sm text-danger">{erreur}</p>}
      {!dossiers && !erreur && <p className="mt-8 text-sm text-subtle">Chargement…</p>}

      <ul className="mt-4">
        {visibles.map((dossier) => (
          <li key={dossier.dossier_id} className="border-b border-hairline">
            <button
              type="button"
              className="flex w-full items-start justify-between gap-8 rounded-lg px-3 py-5 text-left hover:bg-surface-soft"
              onClick={() => {
                setConfirmerRetrait(false);
                setSelection((actuel) => (actuel === dossier.dossier_id ? null : dossier.dossier_id));
              }}
            >
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline gap-2">
                  <span className="truncate text-base font-semibold text-ink">{dossier.nom}</span>
                  <span className="shrink-0 text-sm text-subtle">
                    {dossier.statut_invitation === "actif"
                      ? "Compte ouvert"
                      : dossier.statut_invitation === "invité"
                        ? "Invitation envoyée"
                        : "Compte fermé"}
                  </span>
                </span>
                <span className="mt-3 block space-y-2">
                  <Frise
                    annee={dossier.annee_courante}
                    etape={dossier.etape_courante}
                    compteOuvert={dossier.statut_invitation === "actif"}
                  />
                  <Frise
                    annee={dossier.annee_precedente}
                    etape={dossier.etape_precedente}
                    compteOuvert={dossier.statut_invitation === "actif"}
                  />
                  {[dossier.alerte_regime, dossier.alerte_tva]
                    .filter((alerte): alerte is string => alerte !== null)
                    .map((alerte) => (
                      <span key={alerte} className="block text-sm text-subtle">
                        {alerte}
                      </span>
                    ))}
                </span>
              </span>
              <span
                className={`shrink-0 text-lg font-semibold tabular-nums ${
                  dossier.resultat_cts < 0 ? "text-amount-negative" : "text-amount-positive"
                }`}
              >
                {formatMontant(dossier.resultat_cts)}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {dossiers && visibles.length === 0 && (
        <p className="py-10 text-sm text-subtle">Aucune entreprise pour cette recherche.</p>
      )}

      </div>
      {choisi ? (
        <aside className="flex w-96 shrink-0 flex-col overflow-y-auto border-l border-border bg-canvas p-6">
          <div className="flex items-start justify-between gap-4">
            <h2 className="text-lg font-semibold text-ink">{choisi.nom}</h2>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-danger"
              onClick={() => setConfirmerRetrait(true)}
            >
              Retirer
            </Button>
          </div>
          <p className="mt-1 text-sm text-subtle">{libelleCompte(choisi.statut_invitation)}</p>
          <Link
            href={`/anomalies/${choisi.dossier_id}`}
            className="mt-3 inline-block text-sm font-medium text-primary hover:underline"
          >
            Anomalies
          </Link>
          <dl className="mt-6 space-y-4 text-sm">
            <Ligne libelle="Résultat" valeur={formatMontant(choisi.resultat_cts)} />
            <Ligne libelle="CA HT" valeur={formatMontant(choisi.ca_ht_cts)} />
            <Ligne libelle="Charges" valeur={formatMontant(choisi.charges_cts)} />
            <Ligne libelle="Forme" valeur={choisi.forme_juridique} />
            <Ligne libelle="Imposition" valeur={libelleImposition(choisi.regime_imposition)} />
            <Ligne libelle="Régime de TVA" valeur={libelleRegimeTva(choisi.regime_tva)} />
            <Ligne libelle="TVA sur les recettes" valeur={libelleTvaRecettes(choisi.tva_recettes_regime)} />
            <Ligne libelle="Banque" valeur={libelleBanque(choisi.mode_acces_bancaire)} />
            {choisi.plateformes.length > 0 && (
              <Ligne libelle="Plateformes" valeur={choisi.plateformes.join(", ")} />
            )}
            {choisi.exercice_debut && (
              <Ligne
                libelle="Exercice"
                valeur={
                  choisi.exercice_fin
                    ? `${formatDate(choisi.exercice_debut)} au ${formatDate(choisi.exercice_fin)}`
                    : formatDate(choisi.exercice_debut)
                }
              />
            )}
          </dl>
          <div className="mt-8">
            <p className="text-sm font-medium text-ink">Rappels</p>
            {regles.length === 0 && (
              <p className="mt-2 text-sm text-subtle">
                Aucune règle. Elles se préparent dans Rappels.
              </p>
            )}
            <div className="mt-2 flex flex-wrap gap-2">
              {regles
                .filter(
                  (regle) =>
                    regle.portee !== "selection" || regle.dossier_ids.includes(choisi.dossier_id),
                )
                .map((regle) => (
                <Button
                  key={regle.id}
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={async () => {
                    setInfoRappel(null);
                    try {
                      await declencherRappel(regle.id, choisi.dossier_id);
                      setInfoRappel(`${regle.libelle} enregistré. Envoi prévu quand le canal sera branché.`);
                    } catch (exception) {
                      setInfoRappel(exception instanceof Error ? exception.message : "Échec du rappel.");
                    }
                  }}
                >
                  {regle.libelle}
                </Button>
              ))}
            </div>
            {infoRappel && <p className="mt-2 text-sm text-subtle">{infoRappel}</p>}
          </div>
          {confirmerRetrait && (
            <div className="mt-6 rounded-lg border border-border bg-canvas-app p-4">
              <p className="text-sm text-ink">Retirer {choisi.nom} de la liste ?</p>
              <div className="mt-3 flex justify-end gap-2">
                <Button type="button" variant="ghost" size="sm" onClick={() => setConfirmerRetrait(false)}>
                  Annuler
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  onClick={async () => {
                    await retirerDossier(choisi.dossier_id);
                    setConfirmerRetrait(false);
                    setSelection(null);
                    charger();
                  }}
                >
                  Retirer
                </Button>
              </div>
            </div>
          )}
          <div className="mt-auto flex justify-end pt-8">
            <Button type="button" variant="ghost" size="sm" onClick={() => setSelection(null)}>
              Fermer
            </Button>
          </div>
        </aside>
      ) : null}
    </div>
  );
}

function Total({ libelle, valeur, montant }: { libelle: string; valeur: string; montant?: number }) {
  const couleur =
    montant === undefined ? "text-ink" : montant < 0 ? "text-amount-negative" : "text-amount-positive";
  return (
    <div>
      <dt className="text-sm text-subtle">{libelle}</dt>
      <dd className={`mt-1 text-2xl font-bold tabular-nums tracking-tight ${couleur}`}>{valeur}</dd>
    </div>
  );
}

const ORDRE_COMPTE: FiltreCompte[] = ["tous", "sans_compte", "invite", "ouvert"];
const ORDRE_RESULTAT: FiltreResultat[] = ["tous", "positif", "negatif"];
const LIBELLES_COMPTE: Record<FiltreCompte, string> = {
  tous: "Tous",
  sans_compte: "Sans compte",
  invite: "Invitation envoyée",
  ouvert: "Compte ouvert",
};
const LIBELLES_RESULTAT: Record<FiltreResultat, string> = {
  tous: "Tous",
  positif: "Positif",
  negatif: "Négatif",
};

function Bascule<T extends string>({
  libelle,
  valeur,
  options,
  onChoisir,
}: {
  libelle: string;
  valeur: T;
  options: { id: T; libelle: string }[];
  onChoisir: (id: T) => void;
}) {
  const [ouvert, setOuvert] = useState(false);
  const maintien = useRef(false);
  const minuteur = useRef<number | null>(null);
  const affiche = options.find((option) => option.id === valeur)?.libelle ?? valeur;

  function relacher() {
    if (minuteur.current !== null) window.clearTimeout(minuteur.current);
  }

  return (
    <span className="relative">
      <button
        type="button"
        onPointerDown={() => {
          maintien.current = false;
          minuteur.current = window.setTimeout(() => {
            maintien.current = true;
            setOuvert(true);
          }, 350);
        }}
        onPointerUp={relacher}
        onPointerLeave={relacher}
        onClick={() => {
          if (maintien.current) {
            maintien.current = false;
            return;
          }
          const index = options.findIndex((option) => option.id === valeur);
          const suivant = options[(index + 1) % options.length];
          if (suivant) onChoisir(suivant.id);
        }}
        className="rounded-full border border-border bg-canvas px-3 py-1.5 text-sm text-ink hover:bg-surface-soft"
      >
        <span className="text-subtle">{libelle}</span>
        <span className="mx-1.5 text-faint">·</span>
        {affiche}
      </button>
      {ouvert && (
        <span className="absolute left-0 z-10 mt-1 flex min-w-40 flex-col rounded-lg border border-border bg-canvas py-1 shadow-sm">
          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              className="px-3 py-1.5 text-left text-sm text-ink hover:bg-surface-soft"
              onClick={() => {
                onChoisir(option.id);
                setOuvert(false);
              }}
            >
              {option.libelle}
            </button>
          ))}
        </span>
      )}
    </span>
  );
}

/** Le compte se prépare une fois. Ensuite, par exercice : clôture, signature
 * de validation, dépôt au greffe, dépôt aux impôts, signature légale
 * (doc 02 §4 et §6, doc 19 §5.3, doc 20 §4bis). */
const ETAPES = ["Compte", "Clôture", "Signature", "Greffe", "Impôts", "Signature légale"];

function rangEtape(etape: string, compteOuvert: boolean): number {
  if (etape === "Suivi" || (etape === "Compte" && compteOuvert)) return ETAPES.indexOf("Compte");
  if (etape === "Signé") return ETAPES.indexOf("Greffe");
  const index = ETAPES.indexOf(etape);
  return etape === "Compte" ? -1 : index;
}

function Frise({
  annee,
  etape,
  compteOuvert,
}: {
  annee: number;
  etape: string;
  compteOuvert: boolean;
}) {
  const index = rangEtape(etape, compteOuvert);
  return (
    <span className="flex items-start gap-3">
      <span className="w-8 shrink-0 pt-px text-xs leading-none text-subtle">{annee}</span>
      <span className="grid min-w-0 flex-1 grid-cols-6">
        {ETAPES.map((nom, rang) => {
          const fait = rang <= index;
          const traitFait = rang < index;
          return (
            <span key={nom} className="relative flex flex-col items-center">
              {rang > 0 && (
                <span
                  className={`absolute right-1/2 top-[3px] left-0 h-px ${traitFait || fait ? "bg-primary" : "bg-border"}`}
                />
              )}
              {rang < ETAPES.length - 1 && (
                <span
                  className={`absolute top-[3px] right-0 left-1/2 h-px ${traitFait ? "bg-primary" : "bg-border"}`}
                />
              )}
              <span className={`relative z-10 h-2 w-2 rounded-full ${fait ? "bg-primary" : "bg-border"}`} />
              <span className={`mt-1 text-center text-[10px] leading-tight ${fait ? "text-ink" : "text-subtle"}`}>
                {nom}
              </span>
            </span>
          );
        })}
      </span>
    </span>
  );
}

function Ligne({ libelle, valeur }: { libelle: string; valeur: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-subtle">{libelle}</dt>
      <dd className="text-right text-ink">{valeur}</dd>
    </div>
  );
}

/** doc 14 §2.2 : les connexions qui demandent une action se voient dès
 * l'arrivée, sans aller les chercher. */
function AlerteConnexions() {
  const [nombre, setNombre] = useState(0);
  useEffect(() => {
    lireConnexionsBancaires()
      .then((donnees) =>
        setNombre(
          donnees.dossiers.filter(
            (dossier) =>
              dossier.statut === "expire" ||
              dossier.statut === "a_renouveler" ||
              dossier.sante === "auth_requise",
          ).length,
        ),
      )
      .catch(() => undefined);
  }, []);
  if (nombre === 0) return null;
  return (
    <Link
      href="/connexions-bancaires"
      className="mt-6 block rounded-md border border-warning/40 bg-pending-subtle px-4 py-3 text-sm text-ink hover:border-warning"
    >
      {nombre === 1
        ? "Une connexion bancaire expire ou doit être confirmée."
        : `${nombre} connexions bancaires expirent ou doivent être confirmées.`}{" "}
      <span className="font-medium text-primary">Voir</span>
    </Link>
  );
}
