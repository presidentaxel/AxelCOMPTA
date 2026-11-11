"use client"

import * as React from "react"

import {
  COURBE_GLISSEMENT,
  dureeGlissement,
  positionIndicateur,
  positionIndicateurVertical,
} from "@/lib/indicateur"

/** Filet qui glisse sous l'élément actif d'une rangée d'onglets ou d'entrées
 * de navigation, au lieu d'apparaître d'un coup sous le nouveau (mouvement
 * relevé sur la vidéo de référence, voir `lib/indicateur.ts`).
 *
 * À poser DANS un conteneur `relative`. Il repère lui-même l'élément actif
 * par `selecteur` (`[data-state="active"]` pour Radix Tabs, `[aria-current="page"]`
 * pour la navigation) et se replace quand l'actif change, quand le conteneur
 * ou la police change de taille. Rien n'est à passer en props par onglet. */
export function IndicateurGlissant({
  selecteur,
  axe = "horizontal",
  className = "",
}: {
  selecteur: string
  /** `horizontal` : filet sous une rangée (onglets). `vertical` : filet à
   * gauche d'une colonne (barre latérale), comme le sélecteur de la vidéo. */
  axe?: "horizontal" | "vertical"
  className?: string
}) {
  const reference = React.useRef<HTMLSpanElement>(null)
  const [position, setPosition] = React.useState<{ decalage: number; taille: number } | null>(null)
  const [pret, setPret] = React.useState(false)
  const [reduit, setReduit] = React.useState(false)

  React.useEffect(() => {
    const filet = reference.current
    const conteneur = filet?.parentElement
    if (!filet || !conteneur) return

    const requete = window.matchMedia("(prefers-reduced-motion: reduce)")
    const lireMouvement = () => setReduit(requete.matches)
    lireMouvement()
    requete.addEventListener("change", lireMouvement)

    function placer() {
      const actif = conteneur!.querySelector<HTMLElement>(selecteur)
      if (!actif) return setPosition(null)
      const boite = actif.getBoundingClientRect()
      const cadre = conteneur!.getBoundingClientRect()
      if (axe === "vertical") {
        const { y, hauteur } = positionIndicateurVertical({ top: cadre.top }, { top: boite.top, height: boite.height })
        return setPosition({ decalage: y, taille: hauteur })
      }
      const { x, largeur } = positionIndicateur({ left: cadre.left }, { left: boite.left, width: boite.width })
      setPosition({ decalage: x, taille: largeur })
    }
    placer()
    // Après le premier placement seulement : le navigateur a peint sans
    // transition, les suivants glissent.
    const image = requestAnimationFrame(() => setPret(true))

    const taille = new ResizeObserver(placer)
    taille.observe(conteneur)
    const etat = new MutationObserver(placer)
    etat.observe(conteneur, {
      subtree: true,
      attributes: true,
      attributeFilter: ["data-state", "aria-current"],
    })
    void document.fonts?.ready.then(placer)

    return () => {
      cancelAnimationFrame(image)
      taille.disconnect()
      etat.disconnect()
      requete.removeEventListener("change", lireMouvement)
    }
  }, [selecteur, axe])

  const duree = dureeGlissement(!pret, reduit)
  const vertical = axe === "vertical"
  const decalage = position?.decalage ?? 0
  const taille = position?.taille ?? 0
  return (
    <span
      ref={reference}
      aria-hidden="true"
      data-slot="indicateur-glissant"
      className={`pointer-events-none absolute bg-ink ${
        vertical ? "top-0 left-0 w-0.5" : "-bottom-px left-0 h-0.5"
      } ${className}`}
      style={{
        ...(vertical ? { height: taille } : { width: taille }),
        opacity: position ? 1 : 0,
        transform: vertical ? `translateY(${decalage}px)` : `translateX(${decalage}px)`,
        transitionProperty: "transform, width, height",
        transitionDuration: `${duree}ms`,
        transitionTimingFunction: COURBE_GLISSEMENT,
      }}
    />
  )
}
