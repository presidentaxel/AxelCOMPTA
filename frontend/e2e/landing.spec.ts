import { expect, test, type Page } from "@playwright/test";

/** AXE-949 : la page publique sur `/`. Sans compte, on lit la vitrine, les
 * cinq textes juridiques et on demande un échange. Une session ne quitte
 * pas la vitrine. « Se connecter » ouvre le portefeuille d'un gestionnaire,
 * et la page de connexion pour un chauffeur. L'API est simulée. */

const API = "http://localhost:8000";

function jeton(claims: Record<string, unknown>): string {
  const coder = (valeur: object) => Buffer.from(JSON.stringify(valeur)).toString("base64");
  return `${coder({ alg: "none", typ: "JWT" })}.${coder(claims)}.signature`;
}

async function ouvrirSession(page: Page, cle: string, session: Record<string, unknown>) {
  await page.addInitScript(
    ([k, v]) => window.localStorage.setItem(k as string, v as string),
    [cle, JSON.stringify(session)],
  );
}

const TEXTES = [
  ["Mentions légales", "/legal/mentions-legales"],
  ["Conditions d'utilisation", "/legal/cgu-chauffeur"],
  ["Conditions générales (gestionnaire)", "/legal/cgv-gestionnaire"],
  ["Confidentialité", "/legal/confidentialite"],
  ["Engagement de l'expert-comptable", "/legal/engagement-expert-comptable"],
] as const;

test("sans session, l'accueil est la vitrine et « Se connecter » mène à la connexion", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Vos dossiers VTC arrivent prêts à relire.",
  );
  await page.getByRole("link", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/\/connexion$/u);
});

test("le pied de page donne les cinq textes juridiques, lisibles sans compte", async ({ page }) => {
  await page.goto("/");
  const pied = page.getByRole("navigation", { name: "Informations légales" });
  for (const [titre, chemin] of TEXTES) {
    await expect(pied.getByRole("link", { name: titre })).toHaveAttribute("href", chemin);
  }
  for (const [, chemin] of TEXTES) {
    const reponse = await page.goto(chemin);
    expect(reponse?.status(), chemin).toBe(200);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }
});

test("le texte de confidentialité garde ses blancs « À COMPLÉTER » visibles", async ({ page }) => {
  await page.goto("/legal/confidentialite");
  await expect(page.getByText("À COMPLÉTER").first()).toBeVisible();
});

test("un gestionnaire connecté reste sur la vitrine, « Se connecter » ouvre le portefeuille", async ({
  page,
}) => {
  await page.route(`${API}/**`, (route) => route.abort());
  await ouvrirSession(page, "axelcompta_session_gestionnaire", {
    accessToken: jeton({ app_metadata: { tenant_id: "T1" } }),
    refreshToken: "r",
    tenantId: "T1",
    email: "gestionnaire@exemple.fr",
  });
  await page.goto("/");
  expect(new URL(page.url()).pathname).toBe("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.getByRole("link", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/\/portefeuille/u);
});

test("un chauffeur connecté reste sur la vitrine, « Se connecter » va à la connexion gestionnaire", async ({
  page,
}) => {
  await page.route(`${API}/**`, (route) => route.abort());
  await ouvrirSession(page, "axelcompta_session_chauffeur", {
    accessToken: jeton({ app_metadata: { dossier_id: "D1" } }),
    refreshToken: "r",
    dossierId: "D1",
    email: "chauffeur@exemple.fr",
  });
  await page.goto("/");
  expect(new URL(page.url()).pathname).toBe("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.getByRole("link", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/\/connexion$/u);
});

test("l'aperçu de partage a un titre, une description et une image", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("AxeLCompta · Des dossiers VTC prêts à relire");
  const meta = (propriete: string) =>
    page.locator(`meta[property="${propriete}"]`).getAttribute("content");
  expect(await meta("og:title")).toBe("AxeLCompta · Des dossiers VTC prêts à relire");
  expect(await meta("og:description")).toContain("L'expert-comptable décide");
  expect(await meta("og:image")).toBe("https://compta.axelproject.fr/og-axelcompta.png");
});

test.describe("la demande d'échange", () => {
  async function remplir(page: Page, email = "claire@cabinet-martin.fr") {
    await page.getByLabel("Nom", { exact: true }).fill("Claire Martin");
    await page.getByLabel("E-mail professionnel").fill(email);
    await page.getByLabel("Organisation").fill("Cabinet Martin");
    await page.getByLabel("Un cabinet").check();
  }
  const envoyer = (page: Page) =>
    page.getByRole("button", { name: "Demander un échange de 20 min" }).last().click();

  test("une saisie incomplète dit quoi corriger, sans rien envoyer", async ({ page }) => {
    let appels = 0;
    await page.route(`${API}/demandes-echange`, (route) => {
      appels += 1;
      return route.fulfill({ status: 201, json: { message: "ok" } });
    });
    await page.goto("/#echange");
    await remplir(page, "pas-un-email");
    await envoyer(page);
    await expect(page.locator("form").getByRole("alert")).toHaveText("Indiquez une adresse e-mail valide.");
    await expect(page.getByLabel("E-mail professionnel")).toBeFocused();
    expect(appels).toBe(0);
  });

  test("une demande valide part sans le champ piège rempli, puis on est remercié", async ({ page }) => {
    let corps: Record<string, unknown> | null = null;
    await page.route(`${API}/demandes-echange`, (route) => {
      corps = route.request().postDataJSON() as Record<string, unknown>;
      return route.fulfill({
        status: 201,
        json: { message: "Merci, nous revenons vers vous par e-mail." },
      });
    });
    await page.goto("/#echange");
    await remplir(page);
    await envoyer(page);
    await expect(page.getByRole("status")).toHaveText("Merci, nous revenons vers vous par e-mail.");
    expect(corps).toEqual({
      nom: "Claire Martin",
      email: "claire@cabinet-martin.fr",
      organisation: "Cabinet Martin",
      role: "cabinet",
      message: null,
      site_web: "",
    });
  });

  test("le serveur qui demande de patienter est entendu", async ({ page }) => {
    await page.route(`${API}/demandes-echange`, (route) =>
      route.fulfill({
        status: 429,
        json: { detail: "Trop de demandes pour le moment. Réessayez dans quelques minutes." },
      }),
    );
    await page.goto("/#echange");
    await remplir(page);
    await envoyer(page);
    await expect(page.locator("form").getByRole("alert")).toContainText("Réessayez dans quelques minutes.");
    await expect(page.getByLabel("Nom", { exact: true })).toHaveValue("Claire Martin");
  });

  test("un serveur injoignable est dit, et la saisie est gardée", async ({ page }) => {
    await page.route(`${API}/demandes-echange`, (route) => route.abort());
    await page.goto("/#echange");
    await remplir(page);
    await envoyer(page);
    await expect(page.locator("form").getByRole("alert")).toHaveText(
      "Le serveur ne répond pas. Réessayez dans un instant.",
    );
    await expect(page.getByLabel("Organisation")).toHaveValue("Cabinet Martin");
  });
});

test.describe("sur un téléphone", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test("la page ne défile pas de côté et les actions se touchent au doigt", async ({ page }) => {
    await page.goto("/");
    const defilement = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(defilement).toBeLessThanOrEqual(0);
    for (const nom of ["Demander un échange de 20 min", "Se connecter"]) {
      const boite = await page.getByRole("link", { name: nom }).first().boundingBox();
      expect(boite?.height ?? 0, nom).toBeGreaterThanOrEqual(44);
    }
  });
});
