# -*- coding: utf-8 -*-

import uuid
import logging

# On importe les fonctions de notre agent mémoire pour centraliser l'accès aux fichiers.
from .agent_memoire import lire_donnees_json, ecrire_donnees_json

# La configuration du logging est déjà faite dans main.py, on récupère juste le logger.
logger = logging.getLogger(__name__)

# Le nom du fichier est maintenant la seule chose à connaître, le chemin complet est géré par l'agent mémoire.
NOM_FICHIER_PROJETS = 'projets.json'

def _charger_projets() -> list:
    """Charge la liste des projets via l'agent mémoire."""
    return lire_donnees_json(NOM_FICHIER_PROJETS)

def _sauvegarder_projets(projets: list):
    """Sauvegarde la liste complète des projets via l'agent mémoire."""
    ecrire_donnees_json(NOM_FICHIER_PROJETS, projets)

def lister_projets() -> list:
    """
    Retourne la liste complète de tous les projets.
    Les projets créés avant cette mise à jour n'auront pas les nouveaux champs 
    jusqu'à ce qu'ils soient modifiés.
    """
    logger.debug("💾 PROJETS: Lecture de tous les projets demandée.")
    return _charger_projets()

def ajouter_projet(nom: str, description: str = None, calendrier_associe: str = None, emoji: str = None) -> dict:
    """Ajoute un nouveau projet à la liste, avec une description, un calendrier et un émoji optionnels."""
    logger.info("💾 PROJETS: Tentative d'ajout du projet '%s'.", nom)
    if not nom:
        logger.warning("⚠️ PROJETS: Tentative d'ajout d'un projet sans nom.")
        return {"erreur": "Le nom du projet ne peut pas être vide."}
    
    projets = _charger_projets()
    
    if any(p['nom'].lower() == nom.lower() for p in projets):
        logger.warning("⚠️ PROJETS: Le projet '%s' existe déjà, ajout annulé.", nom)
        return {"erreur": f"Un projet nommé '{nom}' existe déjà."}
        
    nouveau_projet = {
        'id': f'proj_{uuid.uuid4()}',
        'nom': nom,
        'description': description or "",
        'calendrier_associe': calendrier_associe or "",
        'emoji': emoji or None
    }
    projets.append(nouveau_projet)
    _sauvegarder_projets(projets)
    logger.info("✅ PROJETS: Projet '%s' ajouté avec succès.", nom)
    return {"succes": f"Projet '{nom}' ajouté avec succès.", "details": nouveau_projet}

def modifier_projet(id_projet: str, nouveau_nom: str = None, nouvelle_description: str = None, nouveau_calendrier: str = None, nouvel_emoji: str = None) -> dict:
    """
    Modifie un projet existant. Au moins un des champs optionnels doit être fourni.
    Permet de changer le nom, la description, le calendrier associé ou l'émoji.
    Pour effacer un champ, passer une chaîne vide "".
    """
    logger.info("💾 PROJETS: Tentative de modification du projet ID '%s'.", id_projet)
    if nouveau_nom is None and nouvelle_description is None and nouveau_calendrier is None and nouvel_emoji is None:
        logger.warning("⚠️ PROJETS: Modification du projet ID '%s' appelée sans aucun champ à modifier.", id_projet)
        return {"erreur": "Au moins un champ à modifier doit être fourni (nom, description, calendrier ou émoji)."}

    projets = _charger_projets()
    projet_a_modifier = next((p for p in projets if p['id'] == id_projet), None)
    
    if not projet_a_modifier:
        logger.error("🔥 PROJETS: Impossible de modifier, le projet ID '%s' est introuvable.", id_projet)
        return {"erreur": f"Aucun projet trouvé avec l'ID '{id_projet}'."}
    
    # Flag pour savoir si une modification a eu lieu
    modifie = False

    if nouveau_nom is not None:
        if not nouveau_nom:
            return {"erreur": "Le nouveau nom ne peut pas être vide."}
        # Vérifier que le nouveau nom n'est pas déjà pris par un autre projet
        if any(p['nom'].lower() == nouveau_nom.lower() and p['id'] != id_projet for p in projets):
            return {"erreur": f"Un autre projet nommé '{nouveau_nom}' existe déjà."}
        projet_a_modifier['nom'] = nouveau_nom
        modifie = True
        
    if nouvelle_description is not None:
        projet_a_modifier['description'] = nouvelle_description
        modifie = True
        
    if nouveau_calendrier is not None:
        projet_a_modifier['calendrier_associe'] = nouveau_calendrier
        modifie = True
        
    if nouvel_emoji is not None:
        projet_a_modifier['emoji'] = nouvel_emoji
        modifie = True
        
    if modifie:
        _sauvegarder_projets(projets)
        logger.info("✅ PROJETS: Projet ID '%s' mis à jour avec succès.", id_projet)
        return {"succes": f"Projet ID {id_projet} mis à jour.", "details": projet_a_modifier}
    else:
        # Ce cas ne devrait pas être atteint grâce à la vérification initiale, mais c'est une sécurité
        return {"info": "Aucune modification n'a été appliquée."}


def supprimer_projet(id_projet: str) -> dict:
    """Supprime un projet de la liste en utilisant son ID."""
    logger.info("💾 PROJETS: Tentative de suppression du projet ID '%s'.", id_projet)
    projets = _charger_projets()
    projets_avant = len(projets)
    projets_apres = [p for p in projets if p['id'] != id_projet]
    
    if len(projets_apres) == projets_avant:
        logger.error("🔥 PROJETS: Impossible de supprimer, le projet ID '%s' est introuvable.", id_projet)
        return {"erreur": f"Aucun projet trouvé avec l'ID '{id_projet}'."}
        
    _sauvegarder_projets(projets_apres)
    logger.info("✅ PROJETS: Projet ID '%s' supprimé avec succès.", id_projet)
    return {"succes": f"Projet ID {id_projet} supprimé."} 