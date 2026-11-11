"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Etat } from "@/components/Etat";
import {
  listerNotificationsChauffeur,
  marquerNotificationLueChauffeur,
} from "@/lib/auth-chauffeur";
import { phrasePourChauffeur } from "@/lib/langage-chauffeur";
import { messageEchecChargement } from "@/lib/session";
import type { NotificationVue } from "@/lib/types";

const QUAND = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
});

/** Sous le bandeau, au-dessus de la barre du bas, avec une marge. */
const HAUTEUR_PANNEAU = "calc(100dvh - 8rem - env(safe-area-inset-bottom, 0px))";

/** La clôture se valide dans Exercice, la banque se confirme dans Compte,
 * où se choisissent aussi les comptes bancaires (AXE-851).
 * Les opérations à traiter s'ouvrent sur Activité. */
export function lienNotification(dossierId: string, type: string): string {
  if (type === "cloture_a_valider") return `/chauffeur/${dossierId}/exercice`;
  if (type.startsWith("tva_")) return `/chauffeur/${dossierId}/tva`;
  if (type.startsWith("connexion")) return "/chauffeur/compte";
  if (type === "comptes_a_choisir") return "/chauffeur/compte";
  return `/chauffeur/${dossierId}`;
}

/** Notifications internes (doc 19 §5.2). Ouvrir la cloche ne marque rien :
 * chaque notification devient lue quand on l'ouvre. Une erreur de chargement
 * propose de réessayer, un panneau vide renvoie vers l'activité. */
export function Cloche({ dossierId, chemin }: { dossierId: string; chemin: string }) {
  const [notifications, setNotifications] = useState<NotificationVue[]>([]);
  const [statut, setStatut] = useState<"en_cours" | "pret" | "erreur">("en_cours");
  const [message, setMessage] = useState("");
  const [tentative, setTentative] = useState(0);
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
        setStatut("pret");
      })
      .catch((exception: unknown) => {
        if (annule) return;
        setMessage(
          phrasePourChauffeur(
            messageEchecChargement(exception, "Impossible de charger les notifications."),
          ),
        );
        setStatut("erreur");
      });
    return () => {
      annule = true;
    };
  }, [dossierId, chemin, tentative]);

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
        className="relative flex h-11 w-11 items-center justify-center rounded-full text-ink outline-none focus-visible:shadow-focus-detache"
      >
        <Bell className="h-5 w-5" aria-hidden />
        {nonLues > 0 && (
          <span className="absolute right-0 top-0 flex h-5 min-w-5 items-center justify-center rounded-full bg-danger px-1 text-xs font-semibold leading-none text-on-primary">
            {nonLues}
          </span>
        )}
      </button>
      {ouvert && (
        <div
          role="dialog"
          aria-label="Notifications"
          style={{ maxHeight: HAUTEUR_PANNEAU }}
          className="absolute right-0 top-12 z-20 w-72 max-w-[calc(100vw-2rem)] overflow-y-auto overscroll-contain rounded-md border border-border bg-canvas p-2 shadow-md"
        >
          {statut === "erreur" ? (
            <Etat
              type="erreur"
              className="mt-0"
              message={message}
              onReessayer={() => {
                setStatut("en_cours");
                setTentative((valeur) => valeur + 1);
              }}
            />
          ) : statut === "en_cours" ? (
            <Etat type="chargement" className="mt-0">
              <div className="h-11 animate-pulse rounded-md bg-canvas-app" />
            </Etat>
          ) : notifications.length === 0 ? (
            <Etat
              type="vide"
              className="mt-0"
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
                    href={lienNotification(dossierId, notification.type)}
                    onClick={() => suivre(notification)}
                    className="block min-h-11 rounded-md p-3 hover:bg-canvas-app"
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
