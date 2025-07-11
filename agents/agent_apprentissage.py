 # -*- coding: utf-8 -*-

import logging
from .agent_memoire import lire_donnees_json, ecrire_donnees_json

logger = logging.getLogger(__name__)
NOM_FICHIER_APPRENTISSAGES = 'apprentissages.json'

def _charger_apprentissages() -> dict:
    """
    Charge les apprentissages depuis le fichier JSON.
    Retourne un dictionnaire. Si le fichier n'existe pas ou est vide, retourne un dict vide.
    """
    data = lire_donnees_json(NOM_FICHIER_APPRENTISSAGES)
    # On s'assure que c'est bien un dictionnaire qui est retourné
    if not isinstance(data, dict):
        return {}
    return data

def _sauvegarder_apprentissages(apprentissages: dict):
    """Sauvegarde le dictionnaire des apprentissages dans le fichier JSON."""
    ecrire_donnees_json(NOM_FICHIER_APPRENTISSAGES, apprentissages)

def enregistrer_apprentissage(cle: str, valeur: str) -> dict:
    """
    Enregistre ou met à jour une information clé-valeur dans la mémoire persistante.
    La clé est un identifiant unique pour l'information, la valeur est l'information elle-même.
    Exemple: cle='preference_theme', valeur='sombre'.
    """
    logger.info(f"🧠 APPRENTISSAGE: Enregistrement de la clé '{cle}' avec la valeur '{valeur}'.")
    if not isinstance(cle, str) or not isinstance(valeur, str) or not cle or not valeur:
        msg = "La clé et la valeur doivent être des chaînes de caractères non vides."
        logger.error(f"🔥 APPRENTISSAGE: {msg}")
        return {"erreur": msg}
        
    apprentissages = _charger_apprentissages()
    apprentissages[cle] = valeur
    _sauvegarder_apprentissages(apprentissages)
    
    return {"succes": f"Information '{cle}' enregistrée avec succès."}

def consulter_apprentissage(cle: str) -> dict:
    """
    Consulte une information dans la mémoire persistante en utilisant sa clé.
    Retourne la valeur si la clé est trouvée, sinon une erreur.
    """
    logger.debug(f"🧠 APPRENTISSAGE: Consultation de la clé '{cle}'.")
    apprentissages = _charger_apprentissages()
    valeur = apprentissages.get(cle)
    
    if valeur is not None:
        return {"cle": cle, "valeur": valeur}
    else:
        logger.warning(f"⚠️ APPRENTISSAGE: Clé '{cle}' non trouvée dans la mémoire.")
        return {"erreur": f"Aucune information trouvée pour la clé '{cle}'."}

def lister_apprentissages() -> dict:
    """
    Liste toutes les informations (clés et valeurs) enregistrées dans la mémoire persistante.
    """
    logger.debug("🧠 APPRENTISSAGE: Demande de la liste complète des apprentissages.")
    return _charger_apprentissages()

def supprimer_apprentissage(cle: str) -> dict:
    """
    Supprime une information de la mémoire persistante en utilisant sa clé.
    """
    logger.info(f"🧠 APPRENTISSAGE: Tentative de suppression de la clé '{cle}'.")
    apprentissages = _charger_apprentissages()
    
    if cle in apprentissages:
        del apprentissages[cle]
        _sauvegarder_apprentissages(apprentissages)
        return {"succes": f"Information '{cle}' supprimée avec succès."}
    else:
        logger.warning(f"⚠️ APPRENTISSAGE: Clé '{cle}' non trouvée, suppression impossible.")
        return {"erreur": f"Aucune information trouvée pour la clé '{cle}' à supprimer."} 