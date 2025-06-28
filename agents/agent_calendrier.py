# -*- coding: utf-8 -*-

# Importations nécessaires pour la gestion des dates, du système de fichiers et de l'API Google
import datetime
import os.path
import logging

# Importations spécifiques à l'authentification et à l'API Google
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# On importe les fonctions des autres agents dont on a besoin
from .agent_taches import lister_taches
from .agent_projets import lister_projets

# Les "scopes" définissent les permissions que nous demandons.
# Ici, nous demandons la permission de lire et écrire sur le calendrier.
SCOPES = ['https://www.googleapis.com/auth/calendar']
logger = logging.getLogger(__name__)

def _get_credentials():
    """Gère l'authentification et retourne les credentials valides."""
    creds = None
    logger.debug("📅 CALENDRIER: Vérification des identifiants Google.")
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("📅 CALENDRIER: Rafraîchissement du jeton d'accès Google...")
            creds.refresh(Request())
        else:
            logger.info("📅 CALENDRIER: Lancement du flux d'authentification utilisateur pour Google Calendar...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            logger.info("✅ CALENDRIER: Nouveaux identifiants Google sauvegardés dans token.json.")
            token.write(creds.to_json())
    return creds

def lister_tous_les_calendriers() -> list:
    """Récupère la liste de tous les calendriers de l'utilisateur avec leur niveau d'accès."""
    logger.info("📅 CALENDRIER: Récupération de la liste de tous les calendriers et des permissions.")
    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        calendar_list = service.calendarList().list().execute()
        
        formatted_list = []
        for calendar_item in calendar_list.get('items', []):
            formatted_list.append({
                "id": calendar_item['id'],
                "summary": calendar_item['summary'],
                "primary": calendar_item.get('primary', False),
                "access_role": calendar_item.get('accessRole') # owner, writer, reader
            })
        return formatted_list
    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur lors de la récupération de la liste des calendriers: {e}")
        return [{"erreur": str(e)}]

def lister_prochains_evenements(nombre_evenements: int = 10, nom_calendrier: str = None) -> list:
    """
    Liste les 'n' prochains événements. Si nom_calendrier est spécifié,
    cherche dans ce calendrier. Sinon, cherche dans tous les calendriers.
    """
    log_msg = f"📅 CALENDRIER: Récupération des {nombre_evenements} prochains événements"
    if nom_calendrier:
        log_msg += f" dans le calendrier '{nom_calendrier}'."
    else:
        log_msg += " dans tous les calendriers."
    logger.info(log_msg)
    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        
        calendar_ids_to_check = []
        if nom_calendrier:
            all_calendars = lister_tous_les_calendriers()
            target_calendar = next((c for c in all_calendars if nom_calendrier.lower() in c['summary'].lower()), None)
            if not target_calendar:
                return [{"erreur": f"Calendrier '{nom_calendrier}' non trouvé."}]
            calendar_ids_to_check.append(target_calendar['id'])
        else:
            # Si aucun nom n'est donné, on scanne tout
            all_calendars = lister_tous_les_calendriers()
            calendar_ids_to_check = [c['id'] for c in all_calendars]

        all_events = []
        for calendar_id in calendar_ids_to_check:
            events_result = service.events().list(
                calendarId=calendar_id, timeMin=now,
                maxResults=nombre_evenements, singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            for event in events:
                event['calendar_summary'] = next((c['summary'] for c in all_calendars if c['id'] == calendar_id), 'Inconnu')
            all_events.extend(events)

        # Trier tous les événements de tous les calendriers par date de début
        all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
        
        # Formatter les 'n' prochains événements
        formatted_events = []
        for event in all_events[:nombre_evenements]:
            start = event['start'].get('dateTime', event['start'].get('date'))
            formatted_events.append({
                "id": event['id'],
                "summary": event['summary'],
                "start": start,
                "calendar": event['calendar_summary']
            })
        return formatted_events

    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur lors de la récupération des événements: {e}")
        return [{"erreur": str(e)}]

def creer_evenement_calendrier(titre: str, date_heure_debut: str, date_heure_fin: str) -> dict:
    """
    Crée un événement.
    Si le titre correspond à la description d'une tâche existante, il cherche le
    calendrier associé au projet de cette tâche et l'utilise.
    Sinon, il utilise le calendrier principal ('primary').
    """
    logger.info("📅 CALENDRIER: Tentative de création de l'événement '%s'.", titre)
    nom_calendrier_cible = None

    # Logique pour trouver le calendrier associé via la tâche/projet
    taches = lister_taches()
    tache_correspondante = next((t for t in taches if t['description'].lower() == titre.lower()), None)
    
    if tache_correspondante and tache_correspondante.get('projet_id'):
        projets = lister_projets()
        projet_associe = next((p for p in projets if p['id'] == tache_correspondante['projet_id']), None)
        if projet_associe and projet_associe.get('calendrier_associe'):
            nom_calendrier_cible = projet_associe['calendrier_associe']
            logger.info(f"🧠 CALENDRIER: Tâche trouvée. Utilisation du calendrier '{nom_calendrier_cible}' du projet '{projet_associe['nom']}'.")

    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        
        calendar_id = 'primary'  # Par défaut
        if nom_calendrier_cible:
            all_calendars = lister_tous_les_calendriers()
            target_calendar = next((c for c in all_calendars if nom_calendrier_cible.lower() in c['summary'].lower()), None)
            if target_calendar:
                calendar_id = target_calendar['id']
            else:
                logger.warning(f"⚠️ CALENDRIER: Calendrier '{nom_calendrier_cible}' non trouvé, utilisation du calendrier principal.")

        event = {
            'summary': titre,
            'start': {'dateTime': date_heure_debut, 'timeZone': 'Europe/Paris'},
            'end': {'dateTime': date_heure_fin, 'timeZone': 'Europe/Paris'},
        }
        
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info("✅ CALENDRIER: Événement '%s' créé avec succès.", titre)
        return {"succes": f"Événement '{titre}' créé."}
    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur lors de la création de l'événement: {e}")
        return {"erreur": str(e)}

def modifier_evenement_calendrier(event_id: str, nouveau_titre: str = None, nouvelle_date_heure_debut: str = None, nouvelle_date_heure_fin: str = None) -> dict:
    """Modifie un événement existant en se basant sur son ID, en le cherchant uniquement dans les calendriers modifiables."""
    logger.info("📅 CALENDRIER: Tentative de modification de l'événement ID '%s' sur les calendriers modifiables.", event_id)
    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        
        # On ne cherche que dans les calendriers où on a les droits d'écriture
        all_calendars = lister_tous_les_calendriers()
        writable_calendars = [c for c in all_calendars if c.get('access_role') in ['writer', 'owner']]
        if not writable_calendars:
            logger.warning("⚠️ CALENDRIER: Aucune calendrier modifiable trouvé pour ce compte.")
            return {"erreur": "Aucun calendrier modifiable n'a été trouvé."}

        for calendar in writable_calendars:
            calendar_id = calendar['id']
            try:
                # Étape 1: Vérifier si l'événement est dans ce calendrier
                event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

                # Si on arrive ici, on a trouvé l'événement. On le modifie.
                # Étape 2: Mettre à jour les champs
                if nouveau_titre:
                    event['summary'] = nouveau_titre
                if nouvelle_date_heure_debut:
                    event['start']['dateTime'] = nouvelle_date_heure_debut
                if nouvelle_date_heure_fin:
                    event['end']['dateTime'] = nouvelle_date_heure_fin

                # Étape 3: Envoyer la mise à jour
                updated_event = service.events().update(calendarId=calendar_id, eventId=event['id'], body=event).execute()
                
                logger.info("✅ CALENDRIER: Événement ID '%s' modifié avec succès dans le calendrier '%s'.", event_id, calendar['summary'])
                return {"succes": f"Événement '{updated_event['summary']}' mis à jour."}

            except HttpError as e:
                # Si 404, l'événement n'est pas dans CE calendrier, on continue silencieusement.
                if e.resp.status == 404:
                    continue
                # Si c'est une autre erreur (ex: permissions malgré le filtre, rare), on logue.
                logger.error(f"🔥 CALENDRIER: Erreur HTTP en modifiant l'événement ID '{event_id}' dans le calendrier '{calendar['summary']}': {e}")
                # On ne retourne pas l'erreur tout de suite, on continue d'essayer les autres calendriers.

        # Si on a parcouru tous les calendriers sans trouver l'événement
        logger.error("🔥 CALENDRIER: Impossible de modifier, événement introuvable (ID: %s) dans les calendriers modifiables.", event_id)
        return {"erreur": "Événement non trouvé dans vos calendriers modifiables."}

    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur inattendue lors de la modification de l'événement: {e}")
        return {"erreur": str(e)}

def supprimer_evenement_calendrier(event_id: str) -> dict:
    """Supprime un événement en se basant sur son ID, en le cherchant uniquement dans les calendriers modifiables."""
    logger.info("📅 CALENDRIER: Tentative de suppression de l'événement ID '%s' sur les calendriers modifiables.", event_id)
    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)

        # On ne prend que les calendriers où on a les droits d'écriture.
        all_calendars = lister_tous_les_calendriers()
        writable_calendars = [c for c in all_calendars if c.get('access_role') in ['writer', 'owner']]

        if not writable_calendars:
            logger.warning("⚠️ CALENDRIER: Aucun calendrier modifiable trouvé pour ce compte.")
            return {"erreur": "Aucun calendrier modifiable n'a été trouvé."}

        for calendar in writable_calendars:
            calendar_id = calendar['id']
            try:
                service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
                # Si la suppression réussit, on log, on retourne le succès et on arrête la fonction.
                logger.info("✅ CALENDRIER: Événement ID '%s' supprimé avec succès du calendrier '%s'.", event_id, calendar['summary'])
                return {"succes": f"L'événement avec l'ID {event_id} a été supprimé."}
            except HttpError as e:
                # Si l'erreur est 404 (introuvable) ou 410 (déjà supprimé), on continue la recherche.
                if e.resp.status in [404, 410]:
                    continue
                # Si c'est une autre erreur (ex: 403 Forbidden malgré notre filtre), on logue et on continue.
                logger.error(f"🔥 CALENDRIER: Erreur HTTP en supprimant l'événement ID '{event_id}' du calendrier '{calendar['summary']}': {e}")
        
        # Si on a terminé la boucle sans succès, l'événement n'a été trouvé dans aucun calendrier modifiable.
        logger.warning("⚠️ CALENDRIER: Tentative de suppression d'un événement introuvable (ID: %s) dans les calendriers modifiables.", event_id)
        return {"erreur": "Événement non trouvé ou déjà supprimé dans vos calendriers modifiables."}

    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur inattendue lors de la suppression de l'événement: {e}")
        return {"erreur": str(e)}

# Ce bloc s'exécute uniquement si on lance ce fichier directement (pour tester).
if __name__ == '__main__':
    evenements = lister_prochains_evenements()
    if evenements:
        print("\n--- Vos prochains événements ---")
        for ev in evenements:
            print(ev)
        print("-----------------------------\n")
