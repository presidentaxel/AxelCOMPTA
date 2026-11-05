"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  listerNotificationsChauffeur,
  marquerNotificationsLuesChauffeur,
} from "@/lib/auth-chauffeur";
import type { NotificationVue } from "@/lib/types";

const QUAND = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
});

/** Notifications internes (doc 19 §5.2) : pas d'e-mail, la cloche est le
 * canal. Ouvrir la liste vaut lecture. Une erreur de chargement laisse la
 * cloche muette plutôt que de gêner le reste de l'écran. */
export function Cloche({ dossierId, chemin }: { dossierId: string; chemin: string }) {
  const [notifications, setNotifications] = useState<NotificationVue[]>([]);
  const [ouvert, setOuvert] = useState(false);

  useEffect(() => {
    listerNotificationsChauffeur(dossierId)
      .then(setNotifications)
      .catch(() => setNotifications([]));
  }, [dossierId, chemin]);

  const nonLues = notifications.filter((notification) => !notification.lue).length;

  function basculer() {
    const ouvrir = !ouvert;
    setOuvert(ouvrir);
    if (ouvrir && nonLues > 0) {
      marquerNotificationsLuesChauffeur(dossierId)
        .then(() =>
          setNotifications((liste) => liste.map((notification) => ({ ...notification, lue: true }))),
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
        className="relative flex h-11 w-11 items-center justify-center rounded-full text-ink outline-none focus-visible:shadow-[0_0_0_2px_#fff,0_0_0_4px_#2563eb]"
      >
        <Bell className="h-5 w-5" aria-hidden />
        {nonLues > 0 && (
          <span className="absolute right-0 top-0 flex h-5 min-w-5 items-center justify-center rounded-full bg-danger px-1 text-xs font-semibold leading-none text-on-primary">
            {nonLues}
          </span>
        )}
      </button>
      {ouvert && (
        <div className="absolute right-0 top-12 w-72 rounded-lg border border-border bg-canvas p-2 shadow-lg">
          {notifications.length === 0 ? (
            <p className="p-3 text-sm text-subtle">Aucune notification.</p>
          ) : (
            <ul>
              {notifications.map((notification) => (
                <li key={notification.id}>
                  <Link
                    href={`/chauffeur/${dossierId}`}
                    onClick={() => setOuvert(false)}
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
