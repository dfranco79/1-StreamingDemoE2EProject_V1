
################# CONFIFGURACION BASE EN TODOS LOS TIPOS DE INGESTA

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *


# ─── Secrets ────────────────────────────────────────────────────────────
conn_str = dbutils.secrets.get('eventhubs-scope', 'evh-connection-string')

# ─── Configuración del conector Event Hubs ──────────────────────────────
# El conector requiere un dict serializado a JSON
import json

eh_conf = {
    'eventhubs.connectionString': sc._jvm.org.apache.spark.eventhubs
        .EventHubsUtils.encrypt(conn_str),
    'eventhubs.consumerGroup':    '$cg-dlt',
    'eventhubs.startingPosition': json.dumps({
        'offset': '-1',     # -1 = desde el inicio; '@latest' = solo nuevos
        'seqNo':  -1,
        'enqueuedTime': None,
        'isInclusive': True
    }),
    'eventhubs.maxEventsPerTrigger': '1000',   # limita microbatch size
}

# ─── Rutas ADLS Gen2 ────────────────────────────────────────────────────
STORAGE   = 'stgeventhubspoc'
CONTAINER = 'medallion'
BASE_PATH = f'abfss://{CONTAINER}@{STORAGE}.dfs.core.windows.net'

BRONZE_PATH     = f'{BASE_PATH}/bronze/cliente'
SILVER_PATH     = f'{BASE_PATH}/silver/cliente'
GOLD_PATH       = f'{BASE_PATH}/gold/cliente_resumen'

BRONZE_CKPT     = f'{BASE_PATH}/checkpoints/bronze_cliente'
SILVER_CKPT     = f'{BASE_PATH}/checkpoints/silver_cliente'
GOLD_CKPT       = f'{BASE_PATH}/checkpoints/gold_cliente'

###########################################



# ─── 1. Leer con Auto Loader ────────────────────────────────────────────
#
#    format('cloudFiles')  = Auto Loader
#    cloudFiles.format     = formato de los archivos en ADLS
#    cloudFiles.schemaLocation = donde Auto Loader guarda el schema inferido
#    cloudFiles.inferColumnTypes = castea a tipos nativos (no todo string)
#    cloudFiles.maxFilesPerTrigger = cuántos archivos por microbatch

raw_stream = (
    spark.readStream
        .format('cloudFiles')
        .option('cloudFiles.format',           'avro')
        .option('cloudFiles.schemaLocation',   f'{BRONZE_CKPT}/schema')
        .option('cloudFiles.inferColumnTypes', 'true')
        .option('cloudFiles.maxFilesPerTrigger','10')
        # Auto Loader necesita permiso sobre el storage para crear
        # la suscripción de Event Grid. Pasa las credenciales aquí:
        .option('cloudFiles.useNotifications', 'true')  # Event Grid mode
        .option('cloudFiles.subscriptionId',   dbutils.secrets.get('eventhubs-scope', 'sp-subscriptionId'))
        .option('cloudFiles.tenantId',         dbutils.secrets.get('eventhubs-scope', 'sp-tenantId'))
        .option('cloudFiles.clientId',         dbutils.secrets.get('eventhubs-scope', 'sp-clientId'))
        .option('cloudFiles.clientSecret',
            dbutils.secrets.get('eventhubs-scope', 'sp-client-secret')
        )
        .load(LANDING_PATH)
)

# ─── 2. Enriquecer con metadatos del archivo ─────────────────────────────
#    Auto Loader agrega la columna _metadata con info del archivo fuente.
bronze_df = (
    raw_stream
    .withColumn('source_file',    col('_metadata.file_path'))
    .withColumn('file_size',      col('_metadata.file_size'))
    .withColumn('file_modified',  col('_metadata.file_modification_time'))
    .withColumn('ingestion_ts',   current_timestamp())
    .withColumn('source_system',  lit('eventhubs-capture'))
    # Extraer partición del path del archivo
    .withColumn('eh_partition',
        regexp_extract(col('_metadata.file_path'), r'/([0-9]+)/\d{4}/', 1)
    )
    # La columna Body en Avro de Event Hubs es binaria
    .withColumn('raw_payload', col('Body').cast('string'))
    .drop('_metadata')
)

# ─── 3. Escribir Bronze ─────────────────────────────────────────────────
bronze_query = (
    bronze_df.writeStream
        .format('delta')
        .outputMode('append')
        .option('checkpointLocation', BRONZE_CKPT)
        .option('mergeSchema', 'true')
        .partitionBy('eh_partition')
        .trigger(processingTime='5 minutes')  # sincronizado con Capture
        .start(BRONZE_PATH)
)

bronze_query.awaitTermination()
