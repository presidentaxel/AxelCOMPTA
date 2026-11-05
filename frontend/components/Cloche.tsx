"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { EtatErreur, EtatVide } from "@/components/EtatChargement";
import {
  listerNotificationsChauffeur,
  marquerNotificationLueChauffeur,
} from "@/lib/auth-chauffeur";
import { messageVisible } from "@/lib/messages";
import type { NotificationVue } from "@/lib/types";

const QUAND = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
});

/** Notifications internes (doc 19 §5.2) : pas d'e-mail, la cloche est le
 * canal. Chaque notification se lit quand on l'ouvre. */
export function Cloche({ dossierId, chemin }: { dossierId: string; chemin: string }) {
  const [notifications, setNotifications] = useState<NotificationVue[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);
  const [ouvert, setOuvert] = useState(false);
  const [essai, setEssai] = useState(0);
  const panneau = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let annule = false;
    listerNotificationsChauffeur(dossierId)
      .then((liste) => {
        if (!annule) {
          setNotifications(liste);
          setErreur(null);
        }
      })
      .catch((exception: unknown) => {
        if (!annule) {
          setErreur(messageVisible(exception, "Impossible de charger les notifications."));
        }
      });
    return () => {
      annule = true;
    };
  }, [dossierId, chemin, essai]);

  useEffect(() => {
    if (!ouvert) return;
    function surTouche(evenement: KeyboardEvent) {
      if (evenement.key === "Escape") setOuvert(false);
    }
    function surClic(evenement: MouseEvent) {
      if (panneau.current && !panneau.current.contains(evenement.target as Node)) {
        setOuvert(false);
      }
    }
    document.addEventListener("keydown", surTouche);
    document.addEventListener("mousedown", surClic);
    return () => {
      document.removeEventListener("keydown", surTouche);
      document.removeEventListener("mousedown", surClic);
    };
  }, [ouvert]);

  const nonLues = notifications.filter((notification) => !notification.lue).length;

  async function ouvrirUne(notification: NotificationVue) {
    setOuvert(false);
    if (notification.lue) return;
    try {
      await marquerNotificationLueChauffeur(dossierId, notification.id);
      setNotifications((liste) =>
        liste.map((ligne) => (ligne.id === notification.id ? { ...ligne, lue: true } : ligne)),
      );
    } catch {
      // Le lien a déjà mené à l'écran. La pastille se mettra à jour au prochain chargement.
    }
  }

  return (
    <div className="relative ml-auto" ref={panneau}>
      <button
        type="button"
        onClick={() => setOuvert((actuel) => !actuel)}
        aria-expanded={ouvert}
        aria-label={nonLues > 0 ? `Notifications, ${nonLues} non lues` : "Notifications"}
        className="relative flex h-11 w-11 items-center justify-center rounded-full text-ink"
      >
        <Bell className="h-5 w-5" aria-hidden />
        {nonLues > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-xs font-semibold text-on-primary">
            {nonLues}
          </span>
        )}
      </button>
      {ouvert && (
        <div className="absolute right-0 top-12 z-20 max-h-[min(24rem,calc(100dvh-8.5rem-env(safe-area-inset-bottom)))] w-72 overflow-y-auto rounded-lg border border-border bg-canvas p-2 shadow-lg">
          {erreur ? (
            <EtatErreur message={erreur} onReessayer={() => setEssai((n) => n + 1)} />
          ) : notifications.length === 0 ? (
            <EtatVide
              titre="Aucune notification."
              action="Actualiser"
              onAction={() => setEssai((n) => n + 1)}
            />
          ) : (
            <ul>
              {notifications.map((notification) => (
                <li key={notification.id}>
                  <Link
                    href={lienNotification(dossierId, notification.type)}
                    onClick={() => void ouvrirUne(notification)}
                    className="block min-h-11 rounded-md p-3 hover:bg-canvas-app"
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

function lienNotification(dossierId: string, type: string): string {
  if (type === "cloture_a_valider") return `/chauffeur/${dossierId}/exercice`;
  if (type.startsWith("connexion")) return "/chauffeur/compte";
  return `/chauffeur/${dossierId}?vue=traiter`;
}
