"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Squelette } from "@/components/Squelette";
import {
  listerNotificationsChauffeur,
  marquerNotificationsLuesChauffeur,
} from "@/lib/auth-chauffeur";
import { messageEchecChargement } from "@/lib/session";
import type { NotificationVue } from "@/lib/types";

type EtatNotifs =
  | { statut: "en_cours" }
  | { statut: "pret"; valeur: NotificationVue[] }
  | { statut: "erreur"; message: string };

const QUAND = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
});

/** Notifications internes (doc 19 §5.2) : pas d'e-mail, la cloche est le
 * canal. Ouvrir la liste vaut lecture. Un échec s'explique dans le panneau,
 * avec « Réessayer », sans bloquer le reste de l'écran. */
export function Cloche({ dossierId, chemin }: { dossierId: string; chemin: string }) {
  const [tentative, setTentative] = useState(0);
  const [etat, setEtat] = useState<EtatNotifs>({ statut: "en_cours" });
  const [cycle, setCycle] = useState({ dossierId, tentative });
  const [ouvert, setOuvert] = useState(false);
  if (cycle.dossierId !== dossierId || cycle.tentative !== tentative) {
    setCycle({ dossierId, tentative });
    setEtat({ statut: "en_cours" });
  }

  useEffect(() => {
    let annule = false;
    listerNotificationsChauffeur(dossierId)
      .then((valeur) => {
        if (!annule) setEtat({ statut: "pret", valeur });
      })
      .catch((exception: unknown) => {
        if (!annule) {
          setEtat({
            statut: "erreur",
            message: messageEchecChargement(exception, "Impossible de charger les notifications."),
          });
        }
      });
    return () => {
      annule = true;
    };
  }, [dossierId, chemin, tentative]);

  const notifications = etat.statut === "pret" ? etat.valeur : [];
  const nonLues = notifications.filter((notification) => !notification.lue).length;

  function basculer() {
    const ouvrir = !ouvert;
    setOuvert(ouvrir);
    if (ouvrir && nonLues > 0) {
      marquerNotificationsLuesChauffeur(dossierId)
        .then(() =>
          setEtat((actuel) =>
            actuel.statut === "pret"
              ? {
                  statut: "pret",
                  valeur: actuel.valeur.map((notification) => ({ ...notification, lue: true })),
                }
              : actuel,
          ),
        )
        .catch(() => undefined);
    }
  }

  return (
    <div className="relative ml-auto">
      <button
        type="button"
        onClick={basculer}
        aria-expanded={ouvert}
        aria-label={nonLues > 0 ? `Notifications, ${nonLues} non lues` : "Notifications"}
        className="relative flex h-10 w-10 items-center justify-center rounded-full text-ink"
      >
        <Bell className="h-5 w-5" aria-hidden />
        {nonLues > 0 && (
          <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold text-on-primary">
            {nonLues}
          </span>
        )}
      </button>
      {ouvert && (
        <div className="absolute right-0 top-12 w-72 rounded-lg border border-border bg-canvas p-2 shadow-lg">
          {etat.statut === "erreur" ? (
            <Etat
              type="erreur"
              className="mt-0 px-1"
              message={etat.message}
              onReessayer={() => setTentative((valeur) => valeur + 1)}
            />
          ) : etat.statut === "en_cours" ? (
            <Etat type="chargement" className="mt-0 px-1 py-3">
              <Squelette className="h-4 w-full" />
              <Squelette className="mt-2 h-4 w-2/3" />
            </Etat>
          ) : notifications.length === 0 ? (
            <Etat
              type="vide"
              className="mt-0 px-1 py-1"
              message="Aucune notification."
              action={{
                libelle: "Voir mon activité",
                href: `/chauffeur/${dossierId}`,
                onClick: () => setOuvert(false),
              }}
            />
          ) : (
            <ul>
              {notifications.map((notification) => (
                <li key={notification.id}>
                  <Link
                    href={`/chauffeur/${dossierId}`}
                    onClick={() => setOuvert(false)}
                    className="block rounded-md p-3 hover:bg-canvas-app"
                  >
                    <p className={`text-sm ${notification.lue ? "text-subtle" : "font-medium text-ink"}`}>
                      {notification.message}
                    </p>
                    <p className="mt-0.5 text-xs text-subtle">
                      {QUAND.format(new Date(notification.cree_le))}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
