# 10 — Sécurité, RGPD et protection des données

> **État au 2026-11-05** (ajouté ; le reste du doc décrit la cible) :
> - Fait : RLS par dossier sur les tables, pseudonymisation obligatoire
>   avant tout LLM avec tests de fuite (AXE-436), journal d'audit
>   append-only des décisions et signatures, Sentry seulement si un DSN est
>   posé.
> - Pas fait : MFA demandée à la connexion et journal des connexions et
>   exports (AXE-812), sauvegardes avec restauration testée et hébergement
>   de production (AXE-811), isolation de la production, où ne reste qu'un dossier fictif de review UX (AXE-810, doc 17), DPA et
>   CGU (AXE-813), offboarding (export et purge d'un tenant, doc 14 :
>   aucun ticket).

> Statut : brouillon à valider — Dernière mise à jour : 2026-06-12
> Le volet juridique RGPD est traité en doc 02 §8 ; ici, l'implémentation.

## 1. Modèle de menace (résumé)

Actifs à protéger, par ordre de criticité :

1. **Transactions bancaires nominatives** (10 ans d'historique + flux quotidien).
2. **Justificatifs** (peuvent contenir adresses, plaques, données santé par accident).
3. **Intégrité du grand livre** (une altération silencieuse est pire qu'une fuite).
4. Token Digifactory (accès Bridge indirect — doc 16), clés LLM, clé privée Partenaire EDI (à terme).
5. Liens de signature (un lien volé = signature usurpée).

Menaces principales : compromission d'un compte utilisateur B2B, fuite via les
appels LLM, injection via fichiers importés, exfiltration base, erreur interne
(le dev est lui-même une menace : accès prod).

## 2. Mesures structurelles

| Domaine | Mesure |
|---------|--------|
| Chiffrement transit | TLS 1.2+ partout, HSTS, mTLS interne si multi-machines. |
| Chiffrement repos | Disques chiffrés (managé OVH/DO) + chiffrement applicatif (AES-GCM, clés en KMS/Vault) des champs ultra-sensibles : token Digifactory, IBAN complets. |
| Secrets | Jamais en git (gitleaks en CI), injectés par l'environnement, rotation documentée, accès journalisé. |
| Auth B2B | MFA obligatoire, sessions courtes, verrouillage après échecs, journal de connexions visible par l'admin tenant. |
| Liens signataires | URL à jeton unique, expiration ≤ 14 jours, invalidation à usage, re-vérification par code email (OTP) avant affichage des documents. |
| Multi-tenant | RLS PostgreSQL + tests d'isolation automatisés (doc 09 §4). |
| Uploads | Antivirus (ClamAV), validation de type réelle (magic bytes), taille max, pas d'exécution de formules, images re-encodées. |
| Accès prod | Nominatif, par bastion, journalisé ; pas de dump prod sur les laptops — les données de dev sont synthétiques (doc 03 §9). |
| Sauvegardes | PITR Postgres + sauvegardes chiffrées hors-site ; restauration testée trimestriellement. |
| Journal d'audit | Table append-only : qui a vu/modifié/validé/exporté quoi, quand, depuis où. Consultable par tenant. C'est aussi un argument commercial face à une banque. **Tranche faite le 2026-09-24** : `journal_audit` trace les décisions et les signatures (acteur, horodatage, référence), verrouillée en base. Consultations et exports, et l'écran de consultation, restent à faire. |

## 3. Cycle de vie des données (RGPD opérationnel)

| Donnée | Conservation | Sort |
|--------|--------------|------|
| Écritures, FEC, liasses | 10 ans (C. com. L.123-22) | Archivage WORM, puis purge. |
| Justificatifs | 10 ans | Idem. |
| Transactions brutes non comptabilisées | Durée du dossier + 1 an | Purge. |
| Dataset d'entraînement | Pseudonymisé, durée contractuelle | Purge/re-pseudonymisation à la sortie d'un client. |
| Logs applicatifs | 12 mois (sans données nominatives dans les logs — lint des appels de log) | Rotation. |
| Comptes utilisateurs inactifs | 24 mois | Anonymisation. |

Procédures à implémenter : export des données d'un tenant (réversibilité
contractuelle), purge complète d'un tenant, réponse à une demande d'accès d'une
personne concernée (via le client, doc 02 §8).

**Point ouvert — chaîne de sous-traitance à 3 (canal bancaire actuel) :**
chauffeur → Bridge → Digifactory → nous. Le consentement DSP2 signé par le
chauffeur couvre-t-il la retransmission à Digifactory ? Question Art. 28 à
trois parties, non traitée à ce jour, à instruire en phase 0 (doc 02 §3,
doc 16 §6).

## 4. Pseudonymisation avant LLM (module dédié, critique)

Tout appel LLM passe par un module unique `pseudonymize` — il est **impossible**
(par construction, le client LLM n'accepte que le type `PseudonymizedPrompt`)
d'appeler un fournisseur avec du texte brut.

```text
"VIR M. JEAN MARTIN LOC VEHICULE FR76 3000 4000 ..." 
        │
        ▼  détection : NER (noms) + regex strictes (IBAN, cartes, tél, email,
        │  plaques, n° sécu) + dictionnaire des parties connues du dossier (gérant,
        │  société, contreparties récurrentes — connu de nous)
        ▼
"VIR M. {PERSONNE_1} LOC VEHICULE {IBAN_1}"
        │  table de correspondance stockée chez nous, jamais transmise
        ▼
LLM (Claude/Gemini/OpenAI) → réponse → re-substitution locale si nécessaire
```

- Tokens **stables par dossier** (`{PERSONNE_1}` désigne toujours la même personne)
  pour que le LLM puisse raisonner sur la récurrence sans connaître l'identité.
- Le dictionnaire des parties connues (gérants des dossiers, sociétés, client gestionnaire) est notre meilleure
  arme : on n'attend pas que la NER devine, on sait qui chercher.
- **Tests de fuite bloquants en CI** (doc 09 §6) + échantillonnage périodique en
  prod des prompts sortants (revue manuelle d'un échantillon mensuel).
- Réglages fournisseurs : opt-out entraînement, endpoints UE quand disponibles,
  rétention zéro si l'offre existe. Documenté par fournisseur dans un registre.

## 5. Sécurité applicative (SDL)

- OWASP ASVS niveau 2 comme référentiel d'exigences ; checklist par release.
- Dépendances auditées en CI (pip-audit, npm audit) ; alertes critiques = correctif
  sous 48 h.
- Revue de code obligatoire = aussi une revue sécurité (checklist courte dans le
  template de PR : entrées validées ? droits vérifiés ? logs sans PII ?).
- Rate limiting et alerting sur les endpoints sensibles (auth, liens de signature,
  exports).
- Test d'intrusion externe avant la mise en production avec la banque (elle
  l'exigera probablement de toute façon) ; budget à prévoir.

## 6. Réponse à incident (préparée à froid)

- Runbook : détection → coupure (feature flags pour désactiver LLM/exports/liens) →
  investigation (journal d'audit) → notification CNIL ≤ 72 h si violation de
  données personnelles → notification client (délai contractuel à fixer) →
  post-mortem écrit.
- Contacts à jour : DPO, client (canal sécurité), CNIL, hébergeur.
- Exercice sur table une fois par an (2 h, scénario fuite de prompts LLM ou vol
  d'un compte admin tenant).

## 7. Exigences probables d'un client exigeant type secteur financier (à anticiper)

- Questionnaire sécurité fournisseur (ISO 27001-like) : ce document + le 08 et 09
  en sont la matière première.
- Hébergement France/UE, réversibilité, clause d'audit, assurance cyber/RC pro.
- Éventuellement : SSO (OIDC/SAML), filtrage IP, environnement dédié. À chiffrer
  dans l'offre commerciale plutôt qu'à découvrir après signature.
