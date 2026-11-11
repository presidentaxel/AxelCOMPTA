# Textes juridiques d'AxeLCompta

> **Projets, non relus par un juriste.** Rédigés le 2026-11-10 à partir des
> services réellement branchés dans le code (AXE-859). La relecture par un
> juriste, l'acceptation tracée des CGU par le chauffeur et le DPA signé
> sont portés par AXE-813. Ne pas les présenter comme définitifs avant.

| Texte | Pour qui | Affiché dans l'app |
|---|---|---|
| [Mentions légales](mentions-legales.md) | Tout le monde | `/legal/mentions-legales` |
| [Conditions d'utilisation (chauffeur)](cgu-chauffeur.md) | Le dirigeant d'un dossier | `/legal/cgu-chauffeur` |
| [Conditions générales (gestionnaire)](cgv-gestionnaire.md) | Le gestionnaire de portefeuille | `/legal/cgv-gestionnaire` |
| [Confidentialité et sous-traitance](confidentialite.md) | Tout le monde, et annexe DPA (art. 28) | `/legal/confidentialite` |
| [Engagement de l'expert-comptable](engagement-expert-comptable.md) | L'expert-comptable habilité | `/legal/engagement-expert-comptable` |

## Règles

- **Un texte, une version.** Chaque fichier porte sa date de version en
  tête. Toute modification change la date ; l'app affiche la version
  acceptée (AXE-813).
- **Rien d'inventé.** Un fait non tranché (hébergeur applicatif, adresse
  d'un sous-traitant, mécanisme de transfert) reste un blanc
  `[À COMPLÉTER : …]`, jamais une valeur plausible.
- **Les textes suivent le code.** Ajouter un service externe (Rollee, un
  fournisseur de LLM, un nouvel hébergeur) oblige à mettre à jour
  [confidentialite.md](confidentialite.md) dans la même PR. Le test
  `frontend/lib/juridique.test.ts` vérifie les critères d'AXE-859 : Supabase
  (eu-west-1) et Digifactory cités, ni prix ni LLM, Bridge jamais présenté
  comme un appel direct.
- Le texte de l'engagement de l'expert-comptable fait foi dans le code
  (`backend/axelcompta/workflow/expert_comptable.py`, `TEXTE_ENGAGEMENT`) :
  c'est lui que l'expert accepte. Le fichier ici le reprend mot pour mot.
