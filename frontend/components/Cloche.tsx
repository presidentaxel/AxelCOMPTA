"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import {
  listerNotificationsChauffeur,
  marquerNotificationLueChauffeur,
} from "@/lib/auth-chauffeur";
import type { NotificationVue } from "@/lib/types";

const QUAND = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
});

/** Sous le bandeau, au-dessus de la barre du bas, avec une marge. */
const HAUTEUR_PANNEAU = "calc(100dvh - 8rem - env(safe-area-inset-bottom, 0px))";

/** La clôture se valide dans Exercice, la banque se confirme dans Compte.
 * Les opérations à traiter s'ouvrent sur Activité. */
export function lienNotification(dossierId: string, type: string): string {
  if (type === "cloture_a_valider") return `/chauffeur/${dossierId}/exercice`;
  if (type.startsWith("connexion")) return "/chauffeur/compte";
  return `/chauffeur/${dossierId}`;
}

/** Notifications internes (doc 19 §5.2). Ouvrir la cloche ne marque rien :
 * chaque notification devient lue quand on l'ouvre. Une erreur de chargement
 * laisse la cloche muette. */
export function Cloche({ dossierId, chemin }: { dossierId: string; chemin: string }) {
  const [notifications, setNotifications] = useState<NotificationVue[]>([]);
  const [ouvert, setOuvert] = useState(false);
  const racine = useRef<HTMLDivElement>(null);
  const lectures = useRef(new Set<string>());

  useEffect(() => {
    let annule = false;
    listerNotificationsChauffeur(dossierId)
      .then((liste) => {
        if (annule) return;
        setNotifications(
          liste.map((notification) =>
            lectures.current.has(notification.id) ? { ...notification, lue: true } : notification,
          ),
        );
      })
      .catch(() => {
        if (!annule) setNotifications([]);
      });
    return () => {
      annule = true;
    };
  }, [dossierId, chemin]);

  useEffect(() => {
    if (!ouvert) return;
    function fermerSiDehors(event: PointerEvent) {
      if (!racine.current?.contains(event.target as Node)) setOuvert(false);
    }
    function fermerSiEchap(event: KeyboardEvent) {
      if (event.key === "Escape") setOuvert(false);
    }
    document.addEventListener("pointerdown", fermerSiDehors);
    document.addEventListener("keydown", fermerSiEchap);
    return () => {
      document.removeEventListener("pointerdown", fermerSiDehors);
      document.removeEventListener("keydown", fermerSiEchap);
    };
  }, [ouvert]);

  const nonLues = notifications.filter((notification) => !notification.lue).length;

  function suivre(notification: NotificationVue) {
    setOuvert(false);
    if (notification.lue || lectures.current.has(notification.id)) return;
    lectures.current.add(notification.id);
    setNotifications((liste) =>
      liste.map((item) => (item.id === notification.id ? { ...item, lue: true } : item)),
    );
    void marquerNotificationLueChauffeur(dossierId, notification.id).catch(() => {
      lectures.current.delete(notification.id);
    });
  }

  return (
    <div className="relative ml-auto" ref={racine}>
      <button
        type="button"
        onClick={() => setOuvert((actuel) => !actuel)}
        aria-expanded={ouvert}
        aria-haspopup="dialog"
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
        <div
          role="dialog"
          aria-label="Notifications"
          style={{ maxHeight: HAUTEUR_PANNEAU }}
          className="absolute right-0 top-12 z-20 w-72 max-w-[calc(100vw-2rem)] overflow-y-auto overscroll-contain rounded-lg border border-border bg-canvas p-2 shadow-lg"
        >
          {notifications.length === 0 ? (
            <p className="p-3 text-sm text-subtle">Aucune notification.</p>
          ) : (
            <ul>
              {notifications.map((notification) => (
                <li key={notification.id}>
                  <Link
                    href={lienNotification(dossierId, notification.type)}
                    onClick={() => suivre(notification)}
                    className="block rounded-md p-3 hover:bg-canvas-app"
                  >
                    <p
                      className={`text-sm break-words ${notification.lue ? "text-subtle" : "font-medium text-ink"}`}
                    >
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
