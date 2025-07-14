# -*- coding: utf-8 -*-

# Importations nécessaires pour la gestion des dates, du système de fichiers et de l'API Google
import datetime
import os.path
import logging
import pytz # On importe pytz pour gérer les fuseaux horaires de manière robuste
from dateutil import parser # On importe le parseur de date pour comparer les heures de fin

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
            # CORRECTION : On ajoute l'heure de fin !
            end = event['end'].get('dateTime', event['end'].get('date'))
            formatted_events.append({
                "id": event['id'],
                "summary": event['summary'],
                "start": start,
                "end": end, # Champ ajouté
                "calendar": event['calendar_summary']
            })
        return formatted_events

    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur lors de la récupération des événements: {e}")
        return [{"erreur": str(e)}]

def lister_evenements_passes(jours: int = 1) -> list:
    """
    Liste les événements terminés depuis le nombre de jours spécifié.
    Par défaut, cherche les événements des dernières 24 heures.
    Ignore certains calendriers système (ex: "Numéros de semaine").
    """
    log_msg = f"📅 CALENDRIER: Récupération des événements terminés depuis {jours} jour(s)."
    logger.info(log_msg)
    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        
        # CORRECTION : On utilise une heure "aware" (consciente de son fuseau horaire) 
        # pour éviter toute ambiguïté lors de la comparaison avec les heures des événements.
        now = datetime.datetime.now(pytz.utc) 
        time_min = now - datetime.timedelta(days=jours)
        
        # Le formatage ISO gère maintenant correctement le fuseau horaire.
        time_min_iso = time_min.isoformat()
        now_iso = now.isoformat()
        
        # On définit ici une liste de noms de calendriers à ignorer.
        # On utilise des minuscules pour une comparaison insensible à la casse.
        CALENDARS_TO_IGNORE = ['numéros de semaine', 'jours fériés']

        all_calendars = lister_tous_les_calendriers()

        # On filtre la liste des calendriers pour exclure ceux que l'on veut ignorer.
        calendars_a_verifier = [
            cal for cal in all_calendars
            if cal.get('summary', '').lower() not in CALENDARS_TO_IGNORE
        ]
        logger.debug(f"Calendriers à vérifier (après filtrage): {[c['summary'] for c in calendars_a_verifier]}")


        all_events = []
        # On boucle sur les objets calendrier pour avoir accès à leur ID et leur nom
        for calendar in calendars_a_verifier:
            calendar_id = calendar['id']
            calendar_summary = calendar['summary']

            try:
                events_result = service.events().list(
                    calendarId=calendar_id, 
                    timeMin=time_min_iso,
                    timeMax=now_iso,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                events = events_result.get('items', [])
                for event in events:
                    # On ajoute directement les informations du calendrier à l'événement
                    event['calendar_id'] = calendar_id
                    event['calendar_summary'] = calendar_summary
                all_events.extend(events)
            except HttpError as e:
                # Si on n'a pas accès à un calendrier (très rare), on logue et on continue
                logger.warning(f"⚠️ CALENDRIER: Impossible d'accéder au calendrier '{calendar_summary}' (ID: {calendar_id}). Erreur: {e}")
                continue

        # CORRECTION MAJEURE : On filtre maintenant les événements pour ne garder que ceux dont l'heure de fin est passée.
        ended_events = []
        for event in all_events:
            try:
                # On récupère l'heure de fin, qu'elle soit pour un événement d'une journée ou un événement horodaté
                end_time_str = event.get('end', {}).get('dateTime', event.get('end', {}).get('date'))
                if not end_time_str:
                    continue

                # On convertit l'heure de fin en objet datetime "aware" pour une comparaison fiable
                end_time_dt = parser.isoparse(end_time_str)
                if end_time_dt.tzinfo is None:
                    end_time_dt = pytz.utc.localize(end_time_dt)

                # La condition clé : on ne garde l'événement que si son heure de fin est passée
                if end_time_dt < now:
                    ended_events.append(event)
            except Exception as e:
                logger.error(f"🔥 CALENDRIER: Impossible de traiter l'heure de fin pour l'événement '{event.get('summary')}'. Erreur: {e}")
                continue
                
        # On trie les événements terminés par date de début
        ended_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
        
        # On ne garde que les champs utiles
        formatted_events = []
        for event in ended_events:
            # On vérifie que l'événement a bien un titre ('summary') avant de le traiter.
            if 'summary' in event:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                # On utilise maintenant les informations du calendrier qu'on a ajoutées.
                formatted_events.append({
                    "id": event['id'],
                    "summary": event['summary'],
                    "start": start,
                    "end": end,
                    "calendar_summary": event['calendar_summary'],
                    "calendar_id": event['calendar_id']
                })
        return formatted_events

    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur lors de la récupération des événements passés: {e}", exc_info=True)
        return [{"erreur": str(e)}]


def creer_evenement_calendrier(titre: str, date_heure_debut: str, date_heure_fin: str, nom_calendrier_cible: str = None) -> dict:
    """
    Crée un événement. L'heure de début et de fin DOIVENT être fournies.
    La logique de choix du calendrier est maintenant entièrement gérée par l'IA.
    """
    logger.info("📅 CALENDRIER: Tentative de création de l'événement '%s' de %s à %s.", titre, date_heure_debut, date_heure_fin)

    # La logique de calcul de durée par défaut a été supprimée.
    # L'IA est maintenant responsable de fournir une date de fin.

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
                msg = f"Le calendrier '{nom_calendrier_cible}' est introuvable."
                logger.error(f"🔥 CALENDRIER: {msg}")
                return {"erreur": "calendrier_non_trouve", "details": msg}

        event = {
            'summary': titre,
            'start': {'dateTime': date_heure_debut, 'timeZone': 'Europe/Paris'},
            'end': {'dateTime': date_heure_fin, 'timeZone': 'Europe/Paris'},
        }
        
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info("✅ CALENDRIER: Événement '%s' créé avec succès (ID: %s).", titre, created_event.get('id'))
        # On retourne non seulement un succès, mais aussi l'ID de l'événement créé
        return {"succes": f"Événement '{titre}' créé.", "event_id": created_event.get('id')}
    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur lors de la création de l'événement: {e}")
        return {"erreur": str(e)}

def modifier_evenement_calendrier(event_id: str, nouveau_titre: str = None, nouvelle_date_heure_debut: str = None, nouvelle_date_heure_fin: str = None, nouveau_nom_calendrier: str = None) -> dict:
    """
    Modifie un événement existant (titre, date, calendrier).
    Cherche l'événement dans tous les calendriers, puis vérifie les permissions avant de modifier.
    Si nouveau_nom_calendrier est fourni, l'événement est déplacé.
    """
    log_message = f"📅 CALENDRIER: Tentative de modification de l'événement ID '{event_id}'."
    logger.info(log_message)

    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        
        all_calendars = lister_tous_les_calendriers()
        
        source_calendar = None
        event_to_modify = None

        # Étape 1: Trouver l'événement dans N'IMPORTE QUEL calendrier
        for calendar in all_calendars:
            try:
                event = service.events().get(calendarId=calendar['id'], eventId=event_id).execute()
                if event:
                    source_calendar = calendar
                    event_to_modify = event
                    logger.info(f"Trouvé l'événement '{event['summary']}' dans le calendrier '{calendar['summary']}'.")
                    break 
            except HttpError as e:
                if e.resp.status == 404:
                    continue # On continue de chercher
                logger.error(f"Erreur HTTP en cherchant l'événement {event_id} dans {calendar['id']}: {e}")
        
        if not event_to_modify:
            logger.error(f"🔥 CALENDRIER: Impossible de trouver l'événement ID '{event_id}' dans TOUS les calendriers.")
            return {"erreur": f"Événement avec l'ID '{event_id}' introuvable."}

        # Étape 2: VÉRIFIER LES PERMISSIONS du calendrier source
        if source_calendar.get('access_role') not in ['writer', 'owner']:
            msg = f"L'événement se trouve dans le calendrier '{source_calendar['summary']}', qui est en lecture seule. Impossible de le modifier ou de le déplacer."
            logger.warning(f"⚠️ CALENDRIER: {msg}")
            return {"erreur": msg}
        
        source_calendar_id = source_calendar['id']

        # Étape 3: Déplacer l'événement si un nouveau calendrier est spécifié
        if nouveau_nom_calendrier:
            # On utilise 'in' pour une recherche plus souple, comme pour la création d'événement
            destination_calendar = next((c for c in all_calendars if nouveau_nom_calendrier.lower() in c['summary'].lower()), None)
            if not destination_calendar:
                logger.error(f"🔥 CALENDRIER: Calendrier de destination '{nouveau_nom_calendrier}' introuvable.")
                return {"erreur": f"Le calendrier de destination '{nouveau_nom_calendrier}' n'existe pas."}
            
            # On vérifie aussi que le calendrier de destination est modifiable
            if destination_calendar.get('access_role') not in ['writer', 'owner']:
                 msg = f"Le calendrier de destination '{destination_calendar['summary']}' n'est pas modifiable."
                 logger.warning(f"⚠️ CALENDRIER: {msg}")
                 return {"erreur": msg}

            destination_calendar_id = destination_calendar['id']

            if source_calendar_id != destination_calendar_id:
                logger.info(f"Déplacement de l'événement de '{source_calendar_id}' vers '{destination_calendar_id}'.")
                service.events().move(
                    calendarId=source_calendar_id,
                    eventId=event_id,
                    destination=destination_calendar_id
                ).execute()
                source_calendar_id = destination_calendar_id
            else:
                logger.info("L'événement est déjà dans le bon calendrier. Pas de déplacement nécessaire.")

        # Étape 4: Mettre à jour les autres détails de l'événement
        modification_effectuee = False
        if nouveau_titre:
            event_to_modify['summary'] = nouveau_titre
            modification_effectuee = True
        
        # On calcule la nouvelle date de fin AVANT de modifier l'événement
        # si seule la date de début est fournie.
        if nouvelle_date_heure_debut and not nouvelle_date_heure_fin:
            try:
                debut = datetime.datetime.fromisoformat(nouvelle_date_heure_debut.replace('Z', '+00:00'))
                fin = debut + datetime.timedelta(hours=1)
                nouvelle_date_heure_fin = fin.isoformat()
                logger.info(f"💡 CALENDRIER: Heure de fin non fournie pour la modification. Fin recalculée pour durer 1h : {nouvelle_date_heure_fin}")
            except ValueError:
                pass # On laisse la logique existante échouer si le format est invalide

        if nouvelle_date_heure_debut:
            event_to_modify['start'] = {'dateTime': nouvelle_date_heure_debut, 'timeZone': 'Europe/Paris'}
            modification_effectuee = True

        if nouvelle_date_heure_fin:
            if 'dateTime' in event_to_modify['end']:
                event_to_modify['end']['dateTime'] = nouvelle_date_heure_fin
            else:
                event_to_modify['end']['date'] = nouvelle_date_heure_fin
            modification_effectuee = True
        
        if modification_effectuee:
            logger.info("Application des modifications de métadonnées (titre, date)...")
            updated_event = service.events().update(
                calendarId=source_calendar_id,
                eventId=event_id,
                body=event_to_modify
            ).execute()
            logger.info("✅ CALENDRIER: Événement ID '%s' entièrement mis à jour.", event_id)
            return {"succes": f"L'événement '{updated_event['summary']}' a été mis à jour avec succès."}

        if nouveau_nom_calendrier:
             return {"succes": f"L'événement a été déplacé avec succès vers le calendrier '{nouveau_nom_calendrier}'."}

        return {"info": "Aucune modification demandée sur l'événement."}

    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur inattendue lors de la modification de l'événement: {e}", exc_info=True)
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
            try:
                # On s'assure que l'événement est bien dans ce calendrier avant de supprimer
                service.events().get(calendarId=calendar['id'], eventId=event_id).execute()
                service.events().delete(calendarId=calendar['id'], eventId=event_id).execute()
                logger.info("✅ CALENDRIER: Événement ID '%s' supprimé avec succès du calendrier '%s'.", event_id, calendar['summary'])
                return {"succes": "L'événement a été supprimé avec succès."}
            except HttpError as e:
                if e.resp.status == 404:
                    continue  # L'événement n'est pas dans ce calendrier, on passe au suivant.
        
        logger.error("🔥 CALENDRIER: Impossible de supprimer, événement introuvable (ID: %s) dans les calendriers modifiables.", event_id)
        return {"erreur": "Événement non trouvé dans vos calendriers modifiables."}
    
    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur inattendue lors de la suppression de l'événement: {e}")
        return {"erreur": str(e)}

# --- Fonctions de gestion des CALENDRIERS eux-mêmes ---

def creer_calendrier(nom_calendrier: str) -> dict:
    """Crée un nouveau calendrier avec le nom spécifié."""
    logger.info(f"📅 CALENDRIER: Tentative de création du calendrier '{nom_calendrier}'.")
    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)

        # Vérifier si un calendrier avec le même nom existe déjà pour éviter les doublons
        all_calendars = lister_tous_les_calendriers()
        if any(nom_calendrier.lower() == c['summary'].lower() for c in all_calendars):
            msg = f"Un calendrier nommé '{nom_calendrier}' existe déjà."
            logger.warning(f"⚠️ CALENDRIER: {msg}")
            return {"erreur": msg}

        calendar_body = {
            'summary': nom_calendrier,
            'timeZone': 'Europe/Paris'
        }
        created_calendar = service.calendars().insert(body=calendar_body).execute()
        
        logger.info(f"✅ CALENDRIER: Calendrier '{nom_calendrier}' créé avec succès (ID: {created_calendar['id']}).")
        return {"succes": f"Le calendrier '{nom_calendrier}' a été créé."}
    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur lors de la création du calendrier: {e}", exc_info=True)
        return {"erreur": str(e)}

def renommer_calendrier(nom_actuel: str, nouveau_nom: str) -> dict:
    """Renomme un calendrier existant."""
    logger.info(f"📅 CALENDRIER: Tentative de renommage du calendrier '{nom_actuel}' en '{nouveau_nom}'.")
    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)

        all_calendars = lister_tous_les_calendriers()
        calendar_to_rename = next((c for c in all_calendars if c['summary'].lower() == nom_actuel.lower()), None)

        if not calendar_to_rename:
            msg = f"Le calendrier nommé '{nom_actuel}' est introuvable."
            logger.error(f"🔥 CALENDRIER: {msg}")
            return {"erreur": msg}
        
        if calendar_to_rename.get('access_role') not in ['writer', 'owner']:
            return {"erreur": f"Vous n'avez pas les droits pour renommer le calendrier '{nom_actuel}'."}

        body = {'summary': nouveau_nom}
        updated_calendar = service.calendars().patch(calendarId=calendar_to_rename['id'], body=body).execute()
        
        logger.info(f"✅ CALENDRIER: Calendrier '{nom_actuel}' renommé en '{nouveau_nom}'.")
        return {"succes": f"Le calendrier '{nom_actuel}' a été renommé en '{nouveau_nom}'."}
    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur lors du renommage du calendrier: {e}", exc_info=True)
        return {"erreur": str(e)}

def supprimer_calendrier(nom_calendrier: str) -> dict:
    """Supprime un calendrier existant."""
    logger.info(f"📅 CALENDRIER: Tentative de suppression du calendrier '{nom_calendrier}'.")
    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)

        all_calendars = lister_tous_les_calendriers()
        calendar_to_delete = next((c for c in all_calendars if c['summary'].lower() == nom_calendrier.lower()), None)

        if not calendar_to_delete:
            msg = f"Le calendrier nommé '{nom_calendrier}' est introuvable."
            logger.error(f"🔥 CALENDRIER: {msg}")
            return {"erreur": msg}
            
        if calendar_to_delete.get('primary', False):
            return {"erreur": "Impossible de supprimer le calendrier principal."}
            
        if calendar_to_delete.get('access_role') not in ['owner']:
            return {"erreur": f"Vous n'avez pas les droits pour supprimer le calendrier '{nom_calendrier}'. Il faut en être le propriétaire."}

        service.calendars().delete(calendarId=calendar_to_delete['id']).execute()
        
        logger.info(f"✅ CALENDRIER: Le calendrier '{nom_calendrier}' a été supprimé.")
        return {"succes": f"Le calendrier '{nom_calendrier}' a été supprimé avec succès."}
    except Exception as e:
        logger.error(f"🔥 CALENDRIER: Erreur lors de la suppression du calendrier: {e}", exc_info=True)
        return {"erreur": str(e)}

# Ce bloc s'exécute uniquement si on lance ce fichier directement (pour tester).
if __name__ == '__main__':
    evenements = lister_prochains_evenements()
    if evenements:
        print("\n--- Vos prochains événements ---")
        for ev in evenements:
            print(ev)
        print("-----------------------------\n")
