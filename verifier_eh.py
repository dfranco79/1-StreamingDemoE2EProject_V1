# Script de verificación rápida: leer los últimos N eventos del hub
from azure.eventhub import EventHubConsumerClient
import os
from dotenv import load_dotenv
load_dotenv()

conn_str = os.getenv('EH_CONNECTION_STRING')
eh_name  = os.getenv('EH_NAME')

def on_event(partition_context, event):
    if event is None:          # ← agrega esta validación
        return    
    print(f'Partición {partition_context.partition_id}: {event.body_as_str()}')
    partition_context.update_checkpoint(event)

client = EventHubConsumerClient.from_connection_string(
    conn_str, consumer_group='$cg-autoloader', eventhub_name=eh_name
)
with client:
    # Leer durante 10 segundos para verificar
    client.receive(
        on_event=on_event,
        starting_position='-1',   # desde el inicio del retention
        max_wait_time=10
    )
