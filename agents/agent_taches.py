# -*- coding: utf-8 -*-

# On importe les fonctions de notre agent mémoire pour ne pas interagir directement avec les fichiers.
from .agent_memoire import lire_donnees_json, ecrire_donnees_json
from .agent_projets import lister_projets
import uuid # Pour générer des identifiants uniques pour chaque tâche
from datetime import datetime
import logging

NOM_FICHIER_TACHES = 'taches.json'
logger = logging.getLogger(__name__)

def _calculer_priorite(important: bool, urgent: bool) -> str:
    """Calcule la priorité selon la matrice d'Eisenhower."""
    if urgent and important:
        return "P1 : Urgent et Important (À faire)"
    elif not urgent and important:
        return "P2 : Important mais pas Urgent (À planifier)"
    elif urgent and not important:
        return "P3 : Urgent mais pas Important (À déléguer)"
    else:
        return "P4 : Ni Urgent, ni Important (À abandonner/reporter)"

def ajouter_tache(description: str, nom_projet: str = None, important: bool = False, urgent: bool = False, date_echeance: str = None) -> dict:
    """
    Ajoute une nouvelle tâche. Si un nom de projet est fourni,
    tente de lier la tâche au projet correspondant.
    Calcule la priorité en fonction de l'importance et de l'urgence.
    Accepte une date d'échéance optionnelle au format ISO (YYYY-MM-DDTHH:MM:SS).
    """
    logger.info("💾 TÂCHES: Tentative d'ajout de la tâche '%s'.", description)
    taches = lister_taches()
    projet_id = None
    if nom_projet:
        projets = lister_projets()
        for p in projets:
            if p['nom'].lower() == nom_projet.lower():
                projet_id = p['id']
                break

    nouvelle_tache = {
        'id': str(uuid.uuid4()),
        'description': description,
        'statut': 'à faire',
        'projet_id': projet_id,
        'date_creation': datetime.now().isoformat(),
        'date_modification': datetime.now().isoformat(),
        'date_echeance': date_echeance, # Nouveau champ
        'important': important,
        'urgent': urgent,
        'priorite': _calculer_priorite(important, urgent),
        'suivi_envoye': False, # Nouveau champ pour la proactivité
        'google_calendar_event_id': None # Pour la synchronisation avec le calendrier
    }
    taches.append(nouvelle_tache)
    ecrire_donnees_json(NOM_FICHIER_TACHES, taches)
    logger.info("✅ TÂCHES: Tâche '%s' ajoutée avec succès.", description)
    return nouvelle_tache

def lister_taches() -> list:
    """
    Récupère la liste de toutes les tâches, les enrichit, les répare si nécessaire,
    et les trie par ordre de priorité Eisenhower.
    Cette fonction agit comme un "contrôleur qualité" pour les données.
    """
    logger.debug("💾 TÂCHES: Lecture et vérification de toutes les tâches demandées.")
    taches = lire_donnees_json(NOM_FICHIER_TACHES)
    projets = lister_projets()
    
    # On crée un dictionnaire pour trouver rapidement les infos d'un projet par son ID
    projets_map = {p['id']: {'nom': p['nom'], 'emoji': p.get('emoji')} for p in projets}
    
    modifications_effectuees = False

    # On parcourt chaque tâche pour vérifier sa cohérence et la réparer au besoin
    for tache in taches:
        # Contrôle 1 : Cohérence des données de projet
        if tache.get('projet_id'):
            projet_info = projets_map.get(tache['projet_id'])
            if projet_info:
                # Si le nom du projet est manquant ou ne correspond pas, on le corrige
                if tache.get('nom_projet') != projet_info.get('nom'):
                    tache['nom_projet'] = projet_info.get('nom')
                    modifications_effectuees = True
                # Si l'émoji du projet est manquant ou ne correspond pas, on le corrige
                if tache.get('emoji_projet') != projet_info.get('emoji'):
                    tache['emoji_projet'] = projet_info.get('emoji')
                    modifications_effectuees = True
            else: # Le projet associé n'existe plus
                if tache.get('nom_projet') != 'Projet inconnu ou supprimé':
                    tache['nom_projet'] = 'Projet inconnu ou supprimé'
                    modifications_effectuees = True

        # Contrôle 2 : Présence et cohérence de la priorité Eisenhower
        # On vérifie si la priorité est manquante ou si elle est incohérente avec l'importance/urgence.
        importance = tache.get('important', False)
        urgence = tache.get('urgent', False)
        priorite_attendue = _calculer_priorite(importance, urgence)
        
        if tache.get('priorite') != priorite_attendue:
            tache['priorite'] = priorite_attendue
            # On ajoute aussi les booléens s'ils manquaient pour une cohérence totale
            if 'important' not in tache:
                tache['important'] = importance
            if 'urgent' not in tache:
                tache['urgent'] = urgence
            modifications_effectuees = True

    # Si des corrections ont été faites, on sauvegarde le fichier
    if modifications_effectuees:
        logger.info("⚙️ TÂCHES: Le contrôleur qualité a corrigé et sauvegardé des incohérences dans les tâches.")
        ecrire_donnees_json(NOM_FICHIER_TACHES, taches)

    # On trie les tâches par priorité (P1, P2, P3, P4).
    taches.sort(key=lambda x: x.get('priorite', 'P9'))
    
    # Enrichir chaque tâche avec des informations sur ses sous-tâches
    for tache in taches:
        sous_taches = tache.get('sous_taches', [])
        if sous_taches:
            total_sous_taches = len(sous_taches)
            sous_taches_terminees = len([st for st in sous_taches if st.get('statut') == 'terminée'])
            sous_taches_en_cours = len([st for st in sous_taches if st.get('statut') == 'en cours'])
            
            # Ajouter un résumé des sous-tâches à la tâche
            tache['resume_sous_taches'] = {
                'total': total_sous_taches,
                'terminees': sous_taches_terminees,
                'en_cours': sous_taches_en_cours,
                'a_faire': total_sous_taches - sous_taches_terminees - sous_taches_en_cours
            }
            
            # Calculer le pourcentage de progression
            if total_sous_taches > 0:
                tache['progression_sous_taches'] = round((sous_taches_terminees / total_sous_taches) * 100)
            else:
                tache['progression_sous_taches'] = 0
        else:
            tache['resume_sous_taches'] = None
            tache['progression_sous_taches'] = None
            
    return taches

def _trouver_tache(description_tache: str, taches: list) -> dict:
    """Fonction utilitaire pour trouver la tâche la plus pertinente."""
    # Recherche exacte d'abord
    for tache in taches:
        if tache['description'].lower() == description_tache.lower():
            return tache
    # Recherche partielle si pas de correspondance exacte
    for tache in taches:
        if description_tache.lower() in tache['description'].lower():
            return tache
    return None

def modifier_tache(description_actuelle: str, nouvelle_description: str = None, nom_projet: str = None, nouvelle_importance: bool = None, nouvelle_urgence: bool = None, nouvelle_date_echeance: str = None, suivi_envoye: bool = None) -> dict:
    """
    Modifie une tâche. La tâche est identifiée par sa description actuelle.
    Permet de changer la description, le projet, l'importance, l'urgence, la date d'échéance ou le statut du suivi.
    """
    logger.info("💾 TÂCHES: Tentative de modification de la tâche '%s'.", description_actuelle)
    taches = lister_taches()
    tache_a_modifier = _trouver_tache(description_actuelle, taches)

    if not tache_a_modifier:
        logger.error("🔥 TÂCHES: Impossible de modifier, la tâche '%s' est introuvable.", description_actuelle)
        return {"erreur": f"Tâche '{description_actuelle}' non trouvée."}

    modifications_faites = False

    if nouvelle_description:
        tache_a_modifier['description'] = nouvelle_description
        modifications_faites = True

    if nom_projet:
        projets = lister_projets()
        projet_cible = next((p for p in projets if p['nom'].lower() == nom_projet.lower()), None)
        if not projet_cible:
            return {"erreur": f"Projet '{nom_projet}' non trouvé."}
        tache_a_modifier['projet_id'] = projet_cible['id']
        modifications_faites = True

    if nouvelle_date_echeance is not None:
        tache_a_modifier['date_echeance'] = nouvelle_date_echeance
        tache_a_modifier['suivi_envoye'] = False # On ré-arme le suivi !
        modifications_faites = True

    if suivi_envoye is not None:
        tache_a_modifier['suivi_envoye'] = suivi_envoye
        modifications_faites = True

    # Gestion de l'importance et de l'urgence
    if nouvelle_importance is not None:
        tache_a_modifier['important'] = nouvelle_importance
        modifications_faites = True
    if nouvelle_urgence is not None:
        tache_a_modifier['urgent'] = nouvelle_urgence
        modifications_faites = True
    
    # Si l'un des deux a changé, on recalcule la priorité
    if nouvelle_importance is not None or nouvelle_urgence is not None:
        # On s'assure d'avoir les valeurs les plus à jour pour le calcul
        importance = tache_a_modifier.get('important', False)
        urgence = tache_a_modifier.get('urgent', False)
        tache_a_modifier['priorite'] = _calculer_priorite(importance, urgence)

    if modifications_faites:
        tache_a_modifier['date_modification'] = datetime.now().isoformat()
        ecrire_donnees_json(NOM_FICHIER_TACHES, taches)
        logger.info("✅ TÂCHES: Tâche '%s' modifiée avec succès.", description_actuelle)
        return tache_a_modifier
    else:
        return {"info": "Aucune modification demandée."}

def changer_statut_tache(description_tache: str, nouveau_statut: str) -> dict:
    """
    Change le statut d'une tâche ('à faire', 'en cours', 'terminée').
    La tâche est identifiée par sa description.
    """
    statuts_valides = ['à faire', 'en cours', 'terminée', 'annulée']
    if nouveau_statut not in statuts_valides:
        return {"erreur": f"Statut '{nouveau_statut}' non valide. Statuts possibles : {statuts_valides}"}
    
    taches = lister_taches()
    tache_a_modifier = _trouver_tache(description_tache, taches)

    if not tache_a_modifier:
        return {"erreur": f"Tâche '{description_tache}' non trouvée."}

    tache_a_modifier['statut'] = nouveau_statut
    tache_a_modifier['date_modification'] = datetime.now().isoformat()
    ecrire_donnees_json(NOM_FICHIER_TACHES, taches)
    return tache_a_modifier

def supprimer_tache(description_tache: str) -> dict:
    """
    Supprime une tâche en se basant sur sa description.
    Retourne l'ID de l'événement calendrier associé s'il existe, pour permettre sa suppression.
    """
    logger.info("💾 TÂCHES: Tentative de suppression de la tâche '%s'.", description_tache)
    taches = lister_taches()
    tache_a_supprimer = _trouver_tache(description_tache, taches)

    if not tache_a_supprimer:
        logger.error("🔥 TÂCHES: Impossible de supprimer, la tâche '%s' est introuvable.", description_tache)
        return {"erreur": f"Tâche '{description_tache}' non trouvée."}

    event_id = tache_a_supprimer.get('google_calendar_event_id')

    taches.remove(tache_a_supprimer)
    ecrire_donnees_json(NOM_FICHIER_TACHES, taches)
    logger.info("✅ TÂCHES: Tâche '%s' supprimée avec succès.", description_tache)
    
    response = {"succes": f"La tâche '{description_tache}' a été supprimée."}
    if event_id:
        response["google_calendar_event_id"] = event_id
        
    return response

def lier_tache_a_evenement(id_tache: str, id_evenement: str) -> dict:
    """Associe un ID d'événement Google Calendar à une tâche."""
    logger.info("💾 TÂCHES: Liaison de la tâche ID '%s' à l'événement ID '%s'.", id_tache, id_evenement)
    taches = lister_taches()
    tache_a_lier = next((t for t in taches if t['id'] == id_tache), None)

    if not tache_a_lier:
        logger.error("🔥 TÂCHES: Impossible de lier, la tâche ID '%s' est introuvable.", id_tache)
        return {"erreur": f"Tâche avec l'ID '{id_tache}' non trouvée."}

    tache_a_lier['google_calendar_event_id'] = id_evenement
    tache_a_lier['date_modification'] = datetime.now().isoformat()
    ecrire_donnees_json(NOM_FICHIER_TACHES, taches)
    logger.info("✅ TÂCHES: Liaison effectuée avec succès.")
    return {"succes": "Liaison de la tâche à l'événement de calendrier réussie."}

# === FONCTIONS POUR LES SOUS-TÂCHES ===

def ajouter_sous_tache(description_tache_parent: str, description_sous_tache: str, important: bool = False, urgent: bool = False) -> dict:
    """
    Ajoute une sous-tâche à une tâche existante.
    La tâche parent est identifiée par sa description.
    """
    logger.info("💾 SOUS-TÂCHES: Tentative d'ajout de la sous-tâche '%s' à la tâche '%s'.", description_sous_tache, description_tache_parent)
    taches = lister_taches()
    tache_parent = _trouver_tache(description_tache_parent, taches)

    if not tache_parent:
        logger.error("🔥 SOUS-TÂCHES: Impossible d'ajouter, la tâche parent '%s' est introuvable.", description_tache_parent)
        return {"erreur": f"Tâche parent '{description_tache_parent}' non trouvée."}

    # Initialiser le champ sous_taches s'il n'existe pas
    if 'sous_taches' not in tache_parent:
        tache_parent['sous_taches'] = []

    # Vérifier qu'une sous-tâche avec cette description n'existe pas déjà
    for sous_tache in tache_parent['sous_taches']:
        if sous_tache['description'].lower() == description_sous_tache.lower():
            logger.warning("⚠️ SOUS-TÂCHES: Une sous-tâche avec la description '%s' existe déjà.", description_sous_tache)
            return {"erreur": f"Une sous-tâche '{description_sous_tache}' existe déjà dans cette tâche."}

    nouvelle_sous_tache = {
        'id': f'sous_{uuid.uuid4()}',
        'description': description_sous_tache,
        'statut': 'à faire',
        'date_creation': datetime.now().isoformat(),
        'date_modification': datetime.now().isoformat(),
        'important': important,
        'urgent': urgent,
        'priorite': _calculer_priorite(important, urgent)
    }

    tache_parent['sous_taches'].append(nouvelle_sous_tache)
    tache_parent['date_modification'] = datetime.now().isoformat()
    
    ecrire_donnees_json(NOM_FICHIER_TACHES, taches)
    logger.info("✅ SOUS-TÂCHES: Sous-tâche '%s' ajoutée avec succès.", description_sous_tache)
    return {"succes": f"Sous-tâche '{description_sous_tache}' ajoutée à '{description_tache_parent}'.", "details": nouvelle_sous_tache}

def lister_sous_taches(description_tache_parent: str) -> dict:
    """
    Liste toutes les sous-tâches d'une tâche parent.
    Retourne les sous-tâches triées par priorité.
    """
    logger.info("💾 SOUS-TÂCHES: Listage des sous-tâches de '%s'.", description_tache_parent)
    taches = lister_taches()
    tache_parent = _trouver_tache(description_tache_parent, taches)

    if not tache_parent:
        logger.error("🔥 SOUS-TÂCHES: Impossible de lister, la tâche parent '%s' est introuvable.", description_tache_parent)
        return {"erreur": f"Tâche parent '{description_tache_parent}' non trouvée."}

    sous_taches = tache_parent.get('sous_taches', [])
    
    # Trier les sous-tâches par priorité
    sous_taches.sort(key=lambda x: x.get('priorite', 'P9'))
    
    return {"tache_parent": description_tache_parent, "sous_taches": sous_taches}

def _trouver_sous_tache(description_tache_parent: str, id_ou_description_sous_tache: str, taches: list) -> tuple:
    """
    Fonction utilitaire pour trouver une sous-tâche spécifique.
    Retourne un tuple (tache_parent, sous_tache) ou (None, None) si non trouvée.
    """
    tache_parent = _trouver_tache(description_tache_parent, taches)
    if not tache_parent or 'sous_taches' not in tache_parent:
        return None, None

    # Recherche par ID d'abord
    for sous_tache in tache_parent['sous_taches']:
        if sous_tache['id'] == id_ou_description_sous_tache:
            return tache_parent, sous_tache
    
    # Recherche par description exacte
    for sous_tache in tache_parent['sous_taches']:
        if sous_tache['description'].lower() == id_ou_description_sous_tache.lower():
            return tache_parent, sous_tache
    
    # Recherche partielle par description
    for sous_tache in tache_parent['sous_taches']:
        if id_ou_description_sous_tache.lower() in sous_tache['description'].lower():
            return tache_parent, sous_tache
    
    return tache_parent, None

def modifier_sous_tache(description_tache_parent: str, description_sous_tache_actuelle: str, nouvelle_description: str = None, nouvelle_importance: bool = None, nouvelle_urgence: bool = None) -> dict:
    """
    Modifie une sous-tâche existante.
    """
    logger.info("💾 SOUS-TÂCHES: Tentative de modification de la sous-tâche '%s' dans '%s'.", description_sous_tache_actuelle, description_tache_parent)
    taches = lister_taches()
    tache_parent, sous_tache = _trouver_sous_tache(description_tache_parent, description_sous_tache_actuelle, taches)

    if not tache_parent:
        logger.error("🔥 SOUS-TÂCHES: Impossible de modifier, la tâche parent '%s' est introuvable.", description_tache_parent)
        return {"erreur": f"Tâche parent '{description_tache_parent}' non trouvée."}
    
    if not sous_tache:
        logger.error("🔥 SOUS-TÂCHES: Impossible de modifier, la sous-tâche '%s' est introuvable.", description_sous_tache_actuelle)
        return {"erreur": f"Sous-tâche '{description_sous_tache_actuelle}' non trouvée."}

    modifications_faites = False

    if nouvelle_description:
        sous_tache['description'] = nouvelle_description
        modifications_faites = True

    if nouvelle_importance is not None:
        sous_tache['important'] = nouvelle_importance
        modifications_faites = True
    
    if nouvelle_urgence is not None:
        sous_tache['urgent'] = nouvelle_urgence
        modifications_faites = True
    
    # Recalculer la priorité si nécessaire
    if nouvelle_importance is not None or nouvelle_urgence is not None:
        importance = sous_tache.get('important', False)
        urgence = sous_tache.get('urgent', False)
        sous_tache['priorite'] = _calculer_priorite(importance, urgence)

    if modifications_faites:
        sous_tache['date_modification'] = datetime.now().isoformat()
        tache_parent['date_modification'] = datetime.now().isoformat()
        ecrire_donnees_json(NOM_FICHIER_TACHES, taches)
        logger.info("✅ SOUS-TÂCHES: Sous-tâche '%s' modifiée avec succès.", description_sous_tache_actuelle)
        return {"succes": f"Sous-tâche modifiée avec succès.", "details": sous_tache}
    else:
        return {"info": "Aucune modification demandée."}

def changer_statut_sous_tache(description_tache_parent: str, description_sous_tache: str, nouveau_statut: str) -> dict:
    """
    Change le statut d'une sous-tâche ('à faire', 'en cours', 'terminée').
    """
    statuts_valides = ['à faire', 'en cours', 'terminée', 'annulée']
    if nouveau_statut not in statuts_valides:
        return {"erreur": f"Statut '{nouveau_statut}' non valide. Statuts possibles : {statuts_valides}"}
    
    logger.info("💾 SOUS-TÂCHES: Tentative de changement de statut de la sous-tâche '%s' vers '%s'.", description_sous_tache, nouveau_statut)
    taches = lister_taches()
    tache_parent, sous_tache = _trouver_sous_tache(description_tache_parent, description_sous_tache, taches)

    if not tache_parent:
        return {"erreur": f"Tâche parent '{description_tache_parent}' non trouvée."}
    
    if not sous_tache:
        return {"erreur": f"Sous-tâche '{description_sous_tache}' non trouvée."}

    sous_tache['statut'] = nouveau_statut
    sous_tache['date_modification'] = datetime.now().isoformat()
    tache_parent['date_modification'] = datetime.now().isoformat()
    
    ecrire_donnees_json(NOM_FICHIER_TACHES, taches)
    logger.info("✅ SOUS-TÂCHES: Statut de la sous-tâche '%s' changé vers '%s'.", description_sous_tache, nouveau_statut)
    return {"succes": f"Statut de la sous-tâche '{description_sous_tache}' changé vers '{nouveau_statut}'.", "details": sous_tache}

def supprimer_sous_tache(description_tache_parent: str, description_sous_tache: str) -> dict:
    """
    Supprime une sous-tâche d'une tâche parent.
    """
    logger.info("💾 SOUS-TÂCHES: Tentative de suppression de la sous-tâche '%s' de '%s'.", description_sous_tache, description_tache_parent)
    taches = lister_taches()
    tache_parent, sous_tache = _trouver_sous_tache(description_tache_parent, description_sous_tache, taches)

    if not tache_parent:
        return {"erreur": f"Tâche parent '{description_tache_parent}' non trouvée."}
    
    if not sous_tache:
        return {"erreur": f"Sous-tâche '{description_sous_tache}' non trouvée."}

    tache_parent['sous_taches'].remove(sous_tache)
    tache_parent['date_modification'] = datetime.now().isoformat()
    
    ecrire_donnees_json(NOM_FICHIER_TACHES, taches)
    logger.info("✅ SOUS-TÂCHES: Sous-tâche '%s' supprimée avec succès.", description_sous_tache)
    return {"succes": f"Sous-tâche '{description_sous_tache}' supprimée."}
