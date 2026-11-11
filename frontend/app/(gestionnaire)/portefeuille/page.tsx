import { Suspense } from "react";

import { Squelette } from "@/components/Squelette";
import { EcranEntreprises } from "./ecran";

export default function PortefeuillePage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-3" aria-hidden>
          <Squelette className="h-[18px] w-48" />
          <Squelette className="h-[59px] w-[min(28rem,100%)]" />
          <Squelette className="h-[76px] w-full" />
          <Squelette className="h-[76px] w-full" />
        </div>
      }
    >
      <EcranEntreprises />
    </Suspense>
  );
}
