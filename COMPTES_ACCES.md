# Comptes d'accès — Tableau de bord DCB

Mot de passe unique pour tous les comptes de démonstration (sauf `admin`) :

```
DcbDemo2026!
```

> Source : `accounts/management/commands/seed_users.py` (constante `DEMO_PASSWORD`). Pour réinitialiser/recréer ces comptes : `python manage.py seed_users`.

## Compte super-utilisateur (admin Django)

| Identifiant | Accès                                                                                              |
| ----------- | --------------------------------------------------------------------------------------------------- |
| `admin`   | `/admin/` — gestion technique brute (modèles, données). Pas de profil métier (pas d'entité). |

## Direction

| Identifiant   | Entité                              | Rôle     |
| ------------- | ------------------------------------ | --------- |
| `directeur` | Direction Commerciale Business (DCB) | Directeur |

Vue agrégée globale : Performance/Engagement Direction + accès à **toutes** les sections (Support Technique, Guichet Unique, SDRCB).

## Sous-Direction Relation Clients Business (SDRCB)

| Identifiant                  | Entité                                  | Rôle          |
| ---------------------------- | ---------------------------------------- | -------------- |
| `sousdir_relation_clients` | Sous-Direction Relation Clients Business | Sous-Directeur |

### Service Clients Business Abidjan

| Identifiant                              | Rôle                                 |
| ---------------------------------------- | ------------------------------------- |
| `chef_abidjan`                         | Chef de Service                       |
| `cadre_affaires_abidjan_demo`          | Cadre Chargée d'Affaires             |
| `cadre_affaires_abidjan_secteur1_demo` | Cadre Chargée d'Affaires (secteur 1) |
| `cadre_affaires_abidjan_secteur2_demo` | Cadre Chargée d'Affaires (secteur 2) |

### Service Clients Business Intérieur

| Identifiant                                | Rôle                                 |
| ------------------------------------------ | ------------------------------------- |
| `chef_interieur`                         | Chef de Service                       |
| `cadre_affaires_interieur_demo`          | Cadre Chargée d'Affaires             |
| `cadre_affaires_interieur_secteur1_demo` | Cadre Chargée d'Affaires (secteur 1) |
| `cadre_affaires_interieur_secteur2_demo` | Cadre Chargée d'Affaires (secteur 2) |

### Service Clients Stratégiques et Sensibles

| Identifiant                          | Rôle                     |
| ------------------------------------ | ------------------------- |
| `chef_strategiques`                | Chef de Service           |
| `cadre_affaires_strategiques_demo` | Cadre Chargée d'Affaires |

### Service Administration Commerciale

| Identifiant                          | Rôle                       |
| ------------------------------------ | --------------------------- |
| `chef_administration`              | Chef de Service             |
| `assistante_appui_commercial_demo` | Assistante Appui Commercial |

## Sous-Direction Support Technique Business

| Identifiant                   | Entité                                   | Rôle          |
| ----------------------------- | ----------------------------------------- | -------------- |
| `sousdir_support_technique` | Sous-Direction Support Technique Business | Sous-Directeur |

Accès : dashboard "Qualité du réseau" (`/reseau/`) — incidents, travaux, zones industrielles.

### Service Prospection et Suivi de Projets de Raccordements

| Identifiant                               | Rôle               |
| ----------------------------------------- | ------------------- |
| `responsable_raccordement`              | Responsable         |
| `assistant_technique_raccordement_demo` | Assistant Technique |

### Service Technique Installation Intérieure et Industrielle

| Identifiant                               | Rôle               |
| ----------------------------------------- | ------------------- |
| `chef_installation_industrielle`        | Chef de Service     |
| `assistant_technique_installation_demo` | Assistant Technique |

## Sous-Direction Guichet Unique CIE-SODECI

La répartition suit la même logique de pilotage différencié que la SDRCB, mais sur
l'axe **CCGC** (Conseillère Client Grands Comptes : BOGA / DIOMANDE / SYLLA)
plutôt que Direction Régionale :

| Identifiant                             | Rôle                              | Périmètre (CCGC couvertes)          |
| ---------------------------------------- | ---------------------------------- | ------------------------------------ |
| `sousdir_guichet_unique`                 | Sous-Directeur                     | Toutes (BOGA + DIOMANDE + SYLLA)     |
| `cadre_guichet_unique`                   | Cadre Guichet Unique               | **Supervise** BOGA + DIOMANDE        |
| `cadre_charge_affaires_guichet`          | Cadre Chargée d'Affaires           | **Supervise** SYLLA                  |
| `conseiller_grands_comptes_guichet`      | Conseiller Client Grands Comptes   | Individuel — SYLLA                   |
| `conseiller_grands_comptes_guichet_2`    | Conseiller Client Grands Comptes   | Individuel — BOGA                    |
| `conseiller_grands_comptes_guichet_3`    | Conseiller Client Grands Comptes   | Individuel — DIOMANDE                |

Un compte "Conseiller" individuel voit uniquement le portefeuille (opérateurs +
immeubles) de sa propre CCGC. Un "Cadre" voit le cumul des CCGC de son groupe,
sans portefeuille personnel. Le Sous-Directeur et la Direction voient tout le
sous-arbre Guichet Unique. Cf. `prospection/scoping.py` et
`accounts.UserProfile.ccgc_supervisees`.

Accès : Prospection immobilière, Opérateurs, Planning/Agenda de visites
(`/guichet-unique/...`).

## Matrice d'accès par section

| Section                                                   | Direction | SDRCB (+ Services) | Support Technique (+ Services) | Guichet Unique |
| --------------------------------------------------------- | :-------: | :----------------: | :----------------------------: | :------------: |
| Performance/Engagement Direction                          |    ✅    |         ❌         |               ❌               |       ❌       |
| Performance/Engagement Entité (la sienne)                |    ✅    |         ✅         |               —               |       —       |
| Portefeuille clients (`clients:liste_portefeuille`)     |    ✅    |         ✅         |               ❌               |       ❌       |
| Qualité du réseau (`reseau:dashboard`)                |    ✅    |         ❌         |               ✅               |       ❌       |
| Prospection immobilière (`prospection_guichet_unique`) |    ✅    |         ❌         |               ❌               |       ✅       |

Toute tentative d'accès direct à une URL hors périmètre renvoie une erreur **403 (Permission refusée)**.