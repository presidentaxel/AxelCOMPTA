"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Etat } from "@/components/Etat";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { declarerTva, lireTva, parametrerTva } from "@/lib/auth-chauffeur";
import { formatDate, formatMontant } from "@/lib/format";
import { messageEchecChargement } from "@/lib/session";
import { nomPeriode, periodeParDefaut, type PeriodeTva, type TvaVue } from "@/lib/tva";

function aujourdHui(): string {
  return new Date().toISOString().slice(0, 10);
}

/** AXE-805 : la CA3 de chaque période, ligne par ligne, à recopier sur
 * impots.gouv. Le chauffeur dit quand il l'a déposée ; la TVA est alors
 * soldée dans sa comptabilité. */
export default function MaTvaPage() {
  const { dossierId } = useParams<{ dossierId: string }>();
  const [tva, setTva] = useState<TvaVue | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [choisie, setChoisie] = useState<string | null>(null);

  const charger = useCallback(() => {
    setErreur(null);
    lireTva(dossierId)
      .then(setTva)
      .catch((exception: unknown) =>
        setErreur(messageEchecChargement(exception, "Impossible de lire votre TVA.")),
      );
  }, [dossierId]);

  useEffect(() => {
    // Premier chargement à l'ouverture de l'écran.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    charger();
  }, [charger]);

  const periode = useMemo(() => {
    if (!tva) return null;
    return tva.periodes.find((p) => p.cle === choisie) ?? periodeParDefaut(tva.periodes, aujourdHui());
  }, [choisie, tva]);

  if (erreur) return <Etat type="erreur" message={erreur} onReessayer={charger} />;
  if (!tva) {
    return (
      <Etat type="chargement" className="mt-0">
        <Squelette className="h-6 w-40" />
        <Squelette className="mt-6 h-48 w-full" />
      </Etat>
    );
  }

  return (
    <section aria-labelledby="titre-tva">
      <h1 id="titre-tva" className="text-xl font-semibold text-ink">
        Ma TVA
      </h1>
      {!tva.periodicite || !tva.jour_echeance ? (
        <Parametres dossierId={dossierId} onFait={setTva} />
      ) : (
        <>
          <p className="mt-1 text-sm text-subtle">
            Déclaration {tva.periodicite}, à déposer le {tva.jour_echeance} du mois suivant.
          </p>
          <label className="mt-4 block text-sm text-ink">
            Période
            <select
              value={periode?.cle ?? ""}
              onChange={(e) => setChoisie(e.target.value)}
              className="mt-1 block h-11 w-full rounded-md border border-border bg-canvas px-3 text-sm"
            >
              {tva.periodes.map((p) => (
                <option key={p.cle} value={p.cle}>
                  {nomPeriode(p.cle)}
                  {p.declaree ? " · déclarée" : ""}
                </option>
              ))}
            </select>
          </label>
          {periode && <Periode dossierId={dossierId} periode={periode} onFait={setTva} />}
        </>
      )}
    </section>
  );
}

function Periode({
  dossierId,
  periode,
  onFait,
}: {
  dossierId: string;
  periode: PeriodeTva;
  onFait: (tva: TvaVue) => void;
}) {
  const [date, setDate] = useState(aujourdHui());
  const [refus, setRefus] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const terminee = periode.fin < aujourdHui();

  async function declarer(evenement: React.FormEvent) {
    evenement.preventDefault();
    setEnvoi(true);
    setRefus(null);
    try {
      onFait(await declarerTva(dossierId, periode.cle, date));
    } catch (exception) {
      setRefus(exception instanceof Error ? exception.message : "Échec de l'enregistrement.");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <div className="mt-6">
      {periode.echeance && (
        <p className="text-sm text-ink">
          {periode.declaree ? "Déclarée." : `À déposer avant le ${formatDate(periode.echeance)}.`}
        </p>
      )}
      {periode.a_traiter > 0 && (
        <p role="status" className="mt-3 rounded-md border border-warning/40 bg-pending-subtle p-3 text-sm text-ink">
          {periode.a_traiter} opération{periode.a_traiter > 1 ? "s" : ""} de cette période{" "}
          {periode.a_traiter > 1 ? "attendent" : "attend"} encore votre choix : les montants
          ci-dessous peuvent changer.{" "}
          <Link href={`/chauffeur/${dossierId}`} className="font-semibold text-signal underline">
            Les traiter
          </Link>
        </p>
      )}
      <table className="mt-4 w-full text-sm">
        <caption className="sr-only">Déclaration CA3 de {nomPeriode(periode.cle)}</caption>
        <tbody>
          {periode.lignes.map((ligne) => (
            <tr key={`${ligne.numero}-${ligne.libelle}`} className="border-b border-hairline">
              <td className="w-10 py-2 align-top tabular-nums text-subtle">{ligne.numero}</td>
              <td className={`py-2 ${ligne.numero ? "text-ink" : "pl-3 text-subtle"}`}>{ligne.libelle}</td>
              <td className="py-2 text-right tabular-nums text-ink">{formatMontant(ligne.centimes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-subtle">
        Numéros de ligne du formulaire 3310-CA3. Les bases hors taxe par taux (lignes 08, 9B) se
        lisent dans votre chiffre d&apos;affaires de la période.
      </p>
      {!periode.declaree && terminee && (
        <form onSubmit={declarer} className="mt-6 space-y-2">
          <label className="block text-sm text-ink">
            J&apos;ai déposé cette déclaration sur impots.gouv le
            <input
              type="date"
              required
              value={date}
              min={periode.fin}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 block h-11 w-full rounded-md border border-border bg-canvas px-3"
            />
          </label>
          {refus && <p className="text-sm text-danger">{refus}</p>}
          <Button type="submit" disabled={envoi} className="w-full">
            {envoi ? "Enregistrement…" : "Enregistrer le dépôt"}
          </Button>
        </form>
      )}
    </div>
  );
}

function Parametres({ dossierId, onFait }: { dossierId: string; onFait: (tva: TvaVue) => void }) {
  const [periodicite, setPeriodicite] = useState("mensuelle");
  const [jour, setJour] = useState("");
  const [refus, setRefus] = useState<string | null>(null);

  async function enregistrer(evenement: React.FormEvent) {
    evenement.preventDefault();
    setRefus(null);
    try {
      onFait(await parametrerTva(dossierId, periodicite, Number(jour)));
    } catch (exception) {
      setRefus(exception instanceof Error ? exception.message : "Échec de l'enregistrement.");
    }
  }

  return (
    <form onSubmit={enregistrer} className="mt-4 space-y-3 text-sm text-ink">
      <p>
        Indiquez comment vous déclarez la TVA. Le jour d&apos;échéance figure dans votre espace
        professionnel sur impots.gouv (il dépend de votre SIREN).
      </p>
      <label className="block">
        Déclaration
        <select
          value={periodicite}
          onChange={(e) => setPeriodicite(e.target.value)}
          className="mt-1 block h-11 w-full rounded-md border border-border bg-canvas px-3"
        >
          <option value="mensuelle">Chaque mois</option>
          <option value="trimestrielle">Chaque trimestre</option>
        </select>
      </label>
      <label className="block">
        Jour d&apos;échéance (du mois suivant)
        <input
          type="number"
          min={1}
          max={31}
          required
          value={jour}
          onChange={(e) => setJour(e.target.value)}
          className="mt-1 block h-11 w-full rounded-md border border-border bg-canvas px-3"
        />
      </label>
      {refus && <p className="text-danger">{refus}</p>}
      <Button type="submit" className="w-full">
        Enregistrer
      </Button>
    </form>
  );
}
