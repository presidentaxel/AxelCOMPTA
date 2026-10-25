"use client";

import { useEffect } from "react";

import { installerSentry } from "@/lib/sentry";

/** Branche Sentry une fois au chargement. Sans DSN, l'appel ne fait rien. */
export function SentryNavigateur() {
  useEffect(() => {
    installerSentry();
  }, []);
  return null;
}
