import json
import logging
import os
import boto3
import requests
from datetime import datetime
from translation_helper import handle_message_translation
from teams_helper import send_message_to_teams, send_image_teams, send_button_message_to_teams
from db_helper import get_creds
from haptik_helper import get_chat_transcripts
from kendra_helper import search_kendra
from profiler import profile


logger = logging.getLogger()
logger.setLevel(logging.INFO)


lambda_client = boto3.client("lambda")
db_service = boto3.resource("dynamodb")
user_mapping_table = db_service.Table(os.environ.get('teams_mapping_table'))
reverse_mapping_table = db_service.Table(
    os.environ.get('teams_reverse_mapping'))
client_mapping_table = db_service.Table(os.environ.get('client_mapping_table'))


@profile
def lambda_handler(event, context):
    # Analyzes the event and sends the message to user in Teams
    client_id = event.get("client_id")
    itsm = event.get("itsm")
    auth_id = event.get("user")
    payload = event.get("body")
    logger.info(payload)
    auth_mapping_response = reverse_mapping_table.get_item(
        Key={"auth_id": auth_id})
    if "Item" in auth_mapping_response:
        conversation_id = auth_mapping_response.get("Item", {}).get("con_id")
    else:
        logger.error(
            f"Couldn't find the conversation_id for the given auth_id: {auth_id}")
        return

    creds = get_creds(client_id)

    event_name = payload.get('event_name', "")
    is_automated = payload.get("agent", {}).get("is_automated")

    user_response = client_mapping_table.get_item(Key={"client_id": client_id})
    if "Item" in user_response:
        is_translation = user_response.get(
            "Item", {}).get("is_translation", "")
    else:
        logger.info(f"Items not found for the client:   {client_id}")

    if 'webhook_conversation_complete' in event_name:
        logger.info("Received Conversation completed event")
        handle_resolution_event(is_translation, creds, payload,
                                auth_id, is_automated, itsm, client_id, conversation_id)
    elif "message" in event_name:
        logger.info("Received Message event")
        message = payload.get("message", {}).get("body", {}).get("text", "")
        logger.info(message)
        logger.info("Alright! I'll be around if you need more help" in message)
        logger.info(client_id)
        logger.info(client_id == "4")
        if (("Alright! I'll be around if you need more help" in message) and (client_id == "4")):
            logger.info(
                "Handling Ticket termination based on message received")
            payload["message"]["body"]["text"] = message.split("|")[0]
            payload["data"] = {"conversation_no": message.split("|")[1]}
            handle_message_event(is_translation, creds, payload,
                                 auth_id, conversation_id, itsm, client_id)
            handle_resolution_event(is_translation, creds, payload,
                                    auth_id, is_automated, itsm, client_id, conversation_id)
        else:
            handle_message_event(is_translation, creds, payload,
                                 auth_id, conversation_id, itsm, client_id)

    elif "chat_pinned" in event_name:
        logger.info("Received Chat Pinned event")
        handle_pinned_event(is_translation, creds, payload,
                            auth_id, conversation_id)
    else:
        logger.info(f"Received Unsupported event: {event_name}")

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }


def handle_pinned_event(is_translation, creds, payload, auth_id, conversation_id):
    """
    Posts a message in the chat window that a user has entered the conversation
    """
    try:
        agent_name = payload.get("agent", {}).get("name").title()
    except AttributeError:
        agent_name = "IT Agent"
    message = f"----- *{agent_name} has entered the conversation* -----"

    if is_translation:
        logger.info("is_translation is True. Translation function is called")
        message = handle_message_translation(message, auth_id)
    message = handle_message_translation(message, auth_id)
    # response = user_mapping_table.get_item(Key={"con_id": conversation_id})
    user_mapping_table.update_item(
        Key={"con_id": conversation_id},
        UpdateExpression="set agent_name=:a",
        ExpressionAttributeValues={
            ":a": agent_name
        })
    send_message_to_teams(creds, conversation_id, message)
    store_message_in_DB(message, conversation_id, agent_name)


def handle_message_event(is_translation, creds, payload, auth_id, conversation_id, itsm, client_id):
    """
    Handles incoming message event
    """
    logger.info("Handling Message event")
    message = payload.get("message", {}).get("body", {}).get("text", "")
    message_type = payload.get("message", {}).get("body", {}).get("type", "")
    response = user_mapping_table.get_item(Key={"con_id": conversation_id})
    email = response.get("Item", {}).get("user_email")
    query = response.get("Item", {}).get("latest_message")
    try:
        agent_name = payload.get("agent", {}).get("name").title()
    except AttributeError:
        agent_name = "BOT"

    item_list = []
    if 'BOT BREAK' in message or payload.get("message", {}).get("body", {}).get("data", {}).get("intents"):
        item_json = {
                "type": "imBack",
                "title": "Talk to an Agent 💬",
                "value": "Talk to an Agent"
            }
        item_list.append(item_json)
        disambiguation_list = payload.get("message", {}).get("body", {}).get("data", {}).get("intents", [])
        for Item in disambiguation_list:
            item_json = {
                    "type": "imBack",
                    "title": f"{Item} 💬",
                    "value": Item
                }
            item_list.append(item_json)
        return handle_kendra_search(item_list, query, creds, conversation_id, agent_name)

    # if payload.get("message", {}).get("body", {}).get("data", {}).get("intents"):
    #     item_json = {
    #             "type": "imBack",
    #             "title": f"Talk to an Agent 💬",
    #             "value": "Talk to an Agent"
    #         }
    #     item_list.append(item_json)
    #     disambiguation_list = payload.get("message", {}).get("body", {}).get("data", {}).get("intents", [])
    #     for Item in disambiguation_list:
    #         item_json = {
    #                 "type": "imBack",
    #                 "title": f"{Item} 💬",
    #                 "value": Item
    #             }
    #         item_list.append(item_json)
    

    if 'BUTTON' in message_type:
        message_url_items = payload.get("message", {}).get(
            "body", {}).get("data", {}).get("items", [{}])
        for Item in message_url_items:
            thumb_url = Item.get("payload", {}).get("url", "")
            actionable_text = Item.get("actionable_text", "")
            uri = Item.get("uri", "")
            item_type = Item.get("type", "")
            item_message = Item.get("payload", {}).get("message", "")
            if item_type.lower() == "app_action" and uri.lower() == "link":
                if ".pdf" in thumb_url or ".docx" in thumb_url:
                    item_json = {
                        "type": "openUrl",
                        "title": f"{actionable_text} 📎",
                        "value": thumb_url
                    }
                    item_list.append(item_json)
                    store_message_in_DB(
                        "ATTACHMENT", conversation_id, agent_name)
                    if ".pdf" in thumb_url:
                        file_type = "pdf"
                    else:
                        file_type = "docx"
                    ticket_attachment_invoke(
                        file_type, itsm, auth_id, conversation_id, client_id, email, actionable_text, thumb_url)
                else:
                    item_json = {
                        "type": "openUrl",
                        "title": f"{actionable_text} 🔗",
                        "value": thumb_url
                    }
                    item_list.append(item_json)
            elif item_type.lower() == "text_only":
                item_json = {
                    "type": "imBack",
                    "title": f"{actionable_text} 💬",
                    "value": item_message
                }
                item_list.append(item_json)

        if message:
            message = message
        else:
            message = "You can click the below button to download the file."
    elif "CAROUSEL" in message_type:
        logger.info("Invoking Attachment consent to forward the Attachment")
        attachment_list = payload.get("message", {}).get(
            "body", {}).get("data", {}).get("items", [])
        for attachments in attachment_list:
            img_url = attachments.get("thumbnail", {}).get("image", "NA")
            title = attachments.get("title", "Attachment File")
            if ".png" in img_url or ".jpeg" in img_url or ".jpg" in img_url:
                title = title + ".png"
                send_image_teams(creds, conversation_id, img_url, title)
                store_message_in_DB("IMAGE", conversation_id, agent_name)
                ticket_attachment_invoke(
                    "png", itsm, auth_id, conversation_id, client_id, email, title, img_url)
            else:
                logger.info(
                    f"File extension not recognised. Only accepts png, jpeg, jpg\n{img_url}")
        return
    if is_translation:
        logger.info("is_translation is True. Translation function is called")
        message = handle_message_translation(message, auth_id)
    if item_list:
        send_button_message_to_teams(
            item_list, creds, conversation_id, message)
        store_message_in_DB(message, conversation_id, agent_name)
    else:
        send_message_to_teams(creds, conversation_id, message)
        store_message_in_DB(message, conversation_id, agent_name)


def get_image_size(img_url):
    logger.info("Getting the size of the Image")
    response = requests.head(img_url)
    return response.headers["content-length"]


def handle_resolution_event(is_translation, creds, payload, auth_id, is_automated, itsm, client_id, conversation_id):
    """
    Handles webhook_conversation_complete event
    """
    user_name = payload.get("user", {}).get("user_name")
    conversation_number = payload.get("data", {}).get("conversation_no")

    chat_text = get_chat_transcripts(creds, user_name, conversation_number)
    logger.debug(chat_text)

    try:
        agent_name = payload.get("agent", {}).get("name").title()
    except AttributeError:
        agent_name = "BOT"

    message = "----- *This conversation is marked as completed* -----"

    if is_translation:
        logger.info("is_translation is True. Translation function is called")
        message = handle_message_translation(message, auth_id)
    send_message_to_teams(creds, conversation_id, message)
    store_message_in_DB(message, conversation_id, agent_name)
    ticket_data = {
        "itsm": itsm,
        "payload": {
            "client_id": client_id,
            "source": "teams",
            "event": "TICKET_RESOLUTION",
            "conversation_id": conversation_id,
            "chat_history": chat_text,
            "is_automated": is_automated
        }
    }
    logger.debug(f"Data being passed to ticketing function is: {ticket_data}")
    lambda_client.invoke(FunctionName=os.environ.get("ticketing_handler_arn"),
                         InvocationType="Event",
                         Payload=json.dumps(ticket_data))


def store_message_in_DB(message, con_id, agent_name):
    """
    Stores the Chat message in the DB as chat_transcript.
    """
    response = user_mapping_table.get_item(Key={"con_id": con_id})
    if "Item" not in response:
        logger.error(f"User: {con_id} not found in the Table")
        return
    chat_transcript = response.get("Item", {}).get("chat_transcript")
    formatted_time = datetime.now().strftime("%H:%M:%S %d-%m-%Y")
    message = f"{formatted_time} [{agent_name}]: {message}"
    if chat_transcript:
        message = f"{chat_transcript}\n{message}"

    user_mapping_table.update_item(Key={"con_id": con_id},
                                   UpdateExpression="set chat_transcript=:i",
                                   ExpressionAttributeValues={
        ":i": message
    })
    return


def ticket_attachment_invoke(file_type, itsm, auth_id, conversation_id, client_id, email, title, img_url):
    ticket_data = {
        "itsm": itsm,
        "payload": {
            "event": "TICKET_ATTACHMENT",
            "source": "teams",
            "auth_id": auth_id,
            "conversation_id": conversation_id,
            "from_haptik": True,
            "client_id": client_id,
            "email": email,
            "file_type": file_type,
            "file_name": title,
            "file_link": img_url
        }
    }

    logger.info(
        f"Data being passed to ticketing function is: {ticket_data}")
    lambda_client.invoke(FunctionName=os.environ.get("ticketing_handler_arn"),
                         InvocationType="Event",
                         Payload=json.dumps(ticket_data))


def handle_kendra_search(item_list: list, query: str, creds: dict, conversation_id: str, agent_name: str):
    """
    When bot break or disamb message is sent it will query Kendra for results
    """
    message, link = search_kendra(query)
    new_list = []
    if link:
        new_list.append({
            "type": "openUrl",
            "title": "Visit Link 🔗",
            "value": link
        })
    new_list.extend(item_list)
    logger.info(new_list)
    send_button_message_to_teams(new_list, creds, conversation_id, message)
    store_message_in_DB(message, conversation_id, agent_name)
