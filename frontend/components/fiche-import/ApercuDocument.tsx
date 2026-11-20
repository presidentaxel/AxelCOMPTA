"use client";

import { useEffect, useState } from "react";

import { telechargerDocumentImport } from "@/lib/auth-gestionnaire";
import { trouverCadres, type MorceauTexte } from "@/lib/cadres-lecture";

const PAGES_MAX = 6; // un relevé ou une liasse : les premières pages suffisent à relire
const LARGEUR = 720;

type Page = { url: string; largeur: number; hauteur: number; morceaux: MorceauTexte[] };

/** AXE-1015 : le document à côté de sa lecture. Un PDF est dessiné page par
 * page, chaque valeur lue encadrée là où son texte l'imprime ; une image est
 * montrée telle quelle (un scan n'a pas de texte : pas de cadres). */
export function ApercuDocument({
  ficheId,
  documentId,
  lecture,
}: {
  ficheId: string;
  documentId: string;
  lecture: Record<string, unknown>;
}) {
  const [pages, setPages] = useState<Page[] | null>(null);
  const [image, setImage] = useState<string | null>(null);
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    let actif = true;
    const urls: string[] = [];
    (async () => {
      const blob = await telechargerDocumentImport(ficheId, documentId);
      const octets = new Uint8Array(await blob.arrayBuffer());
      if (!(octets[0] === 0x25 && octets[1] === 0x50 && octets[2] === 0x44 && octets[3] === 0x46)) {
        const url = URL.createObjectURL(blob);
        urls.push(url);
        if (actif) setImage(url);
        return;
      }
      const pdfjs = await import("pdfjs-dist");
      pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
      const pdf = await pdfjs.getDocument({ data: octets }).promise;
      const rendues: Page[] = [];
      for (let numero = 1; numero <= Math.min(pdf.numPages, PAGES_MAX); numero++) {
        const page = await pdf.getPage(numero);
        const base = page.getViewport({ scale: 1 });
        const vue = page.getViewport({ scale: LARGEUR / base.width });
        const toile = document.createElement("canvas");
        toile.width = vue.width;
        toile.height = vue.height;
        const contexte = toile.getContext("2d");
        if (!contexte) continue;
        await page.render({ canvasContext: contexte, viewport: vue }).promise;
        const texte = await page.getTextContent();
        const morceaux = texte.items.flatMap((item) => {
          if (!("str" in item)) return [];
          const [x1, y1, x2, y2] = vue.convertToViewportRectangle([
            item.transform[4],
            item.transform[5],
            item.transform[4] + item.width,
            item.transform[5] + item.height,
          ]);
          const x = Math.min(x1, x2);
          const y = Math.min(y1, y2);
          return [{ str: item.str, x, y, largeur: Math.abs(x2 - x1), hauteur: Math.abs(y2 - y1) }];
        });
        rendues.push({
          url: toile.toDataURL(),
          largeur: vue.width,
          hauteur: vue.height,
          morceaux,
        });
      }
      if (actif) setPages(rendues);
    })().catch((exception) => {
      if (actif) setErreur(exception instanceof Error ? exception.message : "Préview impossible.");
    });
    return () => {
      actif = false;
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [ficheId, documentId]);

  if (erreur) return <p className="text-danger">Préview impossible : {erreur}</p>;
  if (image) return <img src={image} alt="Document" className="max-h-[70vh] w-full object-contain" />;
  if (!pages) return <p className="text-subtle">Préview en cours…</p>;
  return (
    <div className="max-h-[75vh] space-y-2 overflow-auto">
      {pages.map((page, rang) => (
        <div key={rang} className="relative" style={{ width: page.largeur, height: page.hauteur }}>
          <img src={page.url} alt={`Page ${rang + 1}`} width={page.largeur} height={page.hauteur} />
          {/* Les cadres suivent la lecture : une valeur corrigée est recherchée à nouveau. */}
          {trouverCadres(page.morceaux, lecture).map((cadre, i) => (
            <span
              key={i}
              title={cadre.champ}
              className="absolute rounded-sm border-2 border-signal bg-signal/10"
              style={{ left: cadre.x - 2, top: cadre.y - 2, width: cadre.largeur + 4, height: cadre.hauteur + 4 }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
