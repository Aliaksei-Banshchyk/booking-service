import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

import json
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from schemas import BrokerMessage

_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, '.env'))

logger = logging.getLogger(__name__)

SERVICE_BUS_WRITE_CONN_STR = os.getenv("SERVICE_BUS_WRITE_CONN_STR")
QUEUE_NAME                 = os.getenv("QUEUE_NAME", "aliakseibanshchyk")


def publish(user_id: int, booking_id: int, message: str) -> BrokerMessage:
    msg = BrokerMessage(
        issue_date_time_utc=datetime.now(timezone.utc),
        user_id=user_id,
        booking_id=booking_id,
        message=message,
    )
    payload = json.dumps({
        "issue_date_time_utc": msg.issue_date_time_utc.isoformat(),
        "user_id": msg.user_id,
        "booking_id": msg.booking_id,
        "message": msg.message,
    })
    try:
        with ServiceBusClient.from_connection_string(SERVICE_BUS_WRITE_CONN_STR) as client:
            with client.get_queue_sender(QUEUE_NAME) as sender:
                sender.send_messages(ServiceBusMessage(payload))
        logger.info("Broker: sent message booking_id=%d", booking_id)
    except Exception as exc:
        logger.error("Broker: failed to send – %s", exc)
    return msg
