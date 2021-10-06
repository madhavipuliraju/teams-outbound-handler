import requests
import logging
import os
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def send_message_to_teams(creds, conversation_id, message):
    # Sends message to Teams
    auth_token = generate_auth_token(creds)
    BASE_URL = creds['teams_base_url']
    send_message_url = f"{BASE_URL}/conversations/{conversation_id}/activities"
    data = {"type": "message", "text": message}
    headers = {"Authorization": auth_token, "Content-Type": "application/json"}
    logger.info(f"Trying to send a message to Teams: {message}")
    try:
        response = requests.request(
            "POST", send_message_url, headers=headers, json=data
        )
        logger.info(f"Send Message to Teams Response status: {response.status_code}")
        logger.info(f"Send Message to Teams Payload: {data}")
        if response.status_code == 201:
            return response.json().get("id")
    except Exception as ex:
        logger.error(f"Exception raised while sending the message to the conversation: {ex}")

def send_button_message_to_teams(item_list, creds, conversation_id, message):
    """
    Sends message to Teams
    """
    auth_token = generate_auth_token(creds)
    BASE_URL = creds['teams_base_url']
    send_message_url = f"{BASE_URL}/conversations/{conversation_id}/activities"
    data = {
        "type":"message",
        "attachments":[
            {
                "contentType":"application/vnd.microsoft.card.hero",
                "content":{
                    "text":message,
                    "buttons": item_list
                }
            }
        ]
    }
    headers = {"Authorization": auth_token, "Content-Type": "application/json"}
    logger.info(f"Trying to send a buttons to Teams: {message}")
    try:
        response = requests.request(
            "POST", send_message_url, headers=headers, json=data
        )
        logger.info(f"Send Button to Teams Response status: {response.status_code}")
        logger.info(f"Send Button to Teams Payload: {data}")
        if response.status_code == 201:
            return response.json().get("id")
    except Exception as ex:
        logger.error(f"Exception raised while sending the message to the conversation: {ex}")

def send_consent(creds, conversation_id, title, image_size):
    """
    Sends consent to the Teams user to either accept or decline the upload of the Attachment
    """
    logger.info("Sending Consent to Teams")
    auth_token = generate_auth_token(creds)
    BASE_URL = creds['teams_base_url']
    send_consent_url = f"{BASE_URL}/conversations/{conversation_id}/activities"
    data = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.teams.card.file.consent",
            "name": title,
            "content": {
                "description": "Consent",
                "sizeInBytes": image_size,
                "acceptContext": {},
                "declineContext": {}
            }
        }]
    }
    headers = {"Authorization": auth_token, "Content-Type": "application/json"}
    logger.info("Trying to send a Consent to Teams")
    try:
        response = requests.request(
            "POST", send_consent_url, headers=headers, json=data
        )
        if response.status_code == 201:
            return response.json().get("id")
    except Exception as ex:
        logger.error(f"Exception raised while sending consent to the conversation: {ex}")


def generate_auth_token(creds):
    """
    Generates the auth token
    """
    url = os.environ.get('auth_token_url')

    payload = {
        "grant_type": "client_credentials",
        "client_id": creds["teams_client_id"],
        "client_secret": creds["teams_client_secret"],
        "scope": creds["teams_scope"]
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code == 200:
        return "Bearer " + response.json().get("access_token")
    else:
        logger.error(f"couldn't generate auth token:\n{response.text}")


def send_image_teams(creds, conversation_id, image_url, image_title):
    """
    Sends Images to Teams
    """
    logger.info("Sending Consent to Teams")
    auth_token = generate_auth_token(creds)
    BASE_URL = creds['teams_base_url']
    send_image_teams_url = f"{BASE_URL}/conversations/{conversation_id}/activities"
    data = json.dumps({
        "type":"message",
        "text":"",
        "attachments":[
            {
                "contentType":"image/png",
                "contentUrl": image_url,
                "name": image_title
            }
        ]
    })
    headers = {"Authorization": auth_token, "Content-Type": "application/json"}
    logger.info("Trying to send a Image to Teams")
    try:
        response = requests.request("POST", send_image_teams_url, headers=headers, data=data)
        if response.status_code == 201:
            return response.json().get("id")
    except Exception as ex:
        logger.error(f"Exception raised while sending image to the conversation: {ex}")

def teams_button_payload(message, thumb_url):
    data = {
        "type":"message",
        "text":"",
        "attachments":[
            {
                "contentType":"application/vnd.microsoft.card.adaptive",
                "content":{
                    "type":"AdaptiveCard",
                    "version":"1.0",
                    "body":[
                    {
                        "type":"TextBlock",
                        "text":message,
                        "separation":"none"
                    }
                    ],
                    "actions":[
                    {
                        "type":"Action.OpenUrl",
                        "url":thumb_url,
                        "title":"Click here"
                    }
                    ]
                }
            }
        ]
    }
    return data
