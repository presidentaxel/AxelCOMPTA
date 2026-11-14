"use client";

import { useState } from "react";

import { urlLogo } from "@/lib/logos";

/** Le nom d'une plateforme et son logo Logo.dev, s'il est configuré. */
export function LogoPlateforme({ nom }: { nom: string }) {
  const url = urlLogo(nom);
  const [rate, setRate] = useState(false);
  return (
    <span className="flex h-6 min-w-0 max-w-full items-center gap-2 text-sm leading-none text-ink">
      {url && (
        <span className="flex h-6 w-6 shrink-0 items-center justify-center">
          {!rate && (
            // Logo.dev sert l'image : next/image exigerait son domaine en config.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={url}
              alt=""
              width={24}
              height={24}
              className="h-6 w-6 object-contain"
              onError={() => setRate(true)}
            />
          )}
        </span>
      )}
      <span className="truncate">{nom}</span>
    </span>
  );
}
