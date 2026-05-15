# Fixtures

Ce dossier contient l'export des custom fields.

## ⚠️ Important

Le fichier `custom_field.json` ne peut PAS être placé directement à la racine de ce dossier car Frappe l'importerait automatiquement à chaque `bench migrate`, ce qui provoque des erreurs de conflit sur les champs existants.

## Fichier d'export

- **`export/custom_field.json`** : Export complet des 609 custom fields du module Be Pay.

Pour utiliser ce fichier sur un nouveau site :
```bash
bench --site [site] import-doc apps/be_pay/be_pay/fixtures/export/custom_field.json
```

## Source de vérité

Les fichiers individuels dans `be_pay/be_pay/custom_field/` sont la source de vérité et sont synchronisés automatiquement par Frappe lors de la migration.
