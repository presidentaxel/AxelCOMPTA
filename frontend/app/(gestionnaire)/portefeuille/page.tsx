import { Suspense } from "react";

import { Squelette } from "@/components/Squelette";
import { EcranEntreprises } from "./ecran";

export default function PortefeuillePage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-3" aria-hidden>
          <Squelette className="h-10 w-48" />
          <Squelette className="h-16 w-full" />
          <Squelette className="h-16 w-full" />
        </div>
      }
    >
      <EcranEntreprises />
    </Suspense>
  );
}
