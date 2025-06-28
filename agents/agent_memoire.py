# -*- coding: utf-8 -*-

import json
import os

# Chemin vers le dossier où sont stockées les données.
MEMOIRE_PATH = 'memoire'

def lire_donnees_json(nom_fichier):
    """
    Lit un fichier JSON depuis le dossier memoire et retourne son contenu.
    Retourne une liste vide si le fichier n'existe pas ou est vide.
    """
    chemin_fichier = os.path.join(MEMOIRE_PATH, nom_fichier)
    try:
        with open(chemin_fichier, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Si le fichier n'existe pas ou est mal formé, on retourne une liste vide.
        return []

def ecrire_donnees_json(nom_fichier, donnees):
    """
    Écrit des données (typiquement une liste de dictionnaires) dans un fichier JSON
    dans le dossier memoire.
    """
    chemin_fichier = os.path.join(MEMOIRE_PATH, nom_fichier)
    # S'assure que le dossier memoire existe.
    os.makedirs(MEMOIRE_PATH, exist_ok=True)
    with open(chemin_fichier, 'w', encoding='utf-8') as f:
        # 'indent=4' pour que le fichier soit lisible par un humain.
        # 'ensure_ascii=False' pour bien gérer les caractères spéciaux (accents, etc.).
        json.dump(donnees, f, indent=4, ensure_ascii=False)
