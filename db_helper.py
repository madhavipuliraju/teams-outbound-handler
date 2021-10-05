import boto3
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)


db_service = boto3.resource("dynamodb")

client_mapping_table = db_service.Table(os.environ.get("client_mapping_table"))


def get_creds(client_id):
    """
    Returns the configured Teams Creds channel
    """
    logger.info(f"checking the client info for client: {client_id}")
    response = client_mapping_table.get_item(Key={"client_id": client_id})
    logger.debug(f"Response of client_id mapping: {response}")
    creds = {}
    if "Item" in response:
        creds["teams_base_url"] = response.get("Item", {}).get("teams_base_url")
        creds["teams_client_id"] = response.get("Item", {}).get("teams_client_id")
        creds["teams_client_secret"] = response.get("Item", {}).get("teams_client_secret")
        creds["teams_scope"] = response.get("Item", {}).get("teams_scope")
        creds["bot_business"] = response.get("Item", {}).get("bot_business")
        creds["bot_client_id"] = response.get("Item", {}).get("bot_client_id")
        creds["bot_chat_auth"] = response.get("Item", {}).get("bot_chat_auth")
        return creds
    else:
        logger.error(f"Creds not found for client_id: {client_id}")
