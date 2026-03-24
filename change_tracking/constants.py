# ─── Configurar acceso a ADLS Gen2 ─────────────────────────────────────
store_key = dbutils.secrets.get('eventhubs-scope', 'storage-account-key')

spark.conf.set(
    'fs.azure.account.key.stgeventhubspoc.dfs.core.windows.net',
    store_key
)

# ─── Rutas ──────────────────────────────────────────────────────────────
STORAGE      = 'stgeventhubspoc'
LANDING_PATH = 'abfss://landing@stgeventhubspoc.dfs.core.windows.net/evhns-streaming-poc/evh-cliente'
BASE_PATH    = 'abfss://medallion@stgeventhubspoc.dfs.core.windows.net'

BRONZE_PATH  = f'{BASE_PATH}/bronze/cliente_avro'
SILVER_PATH  = f'{BASE_PATH}/silver/cliente_avro'
GOLD_PATH    = f'{BASE_PATH}/gold/cliente_avro'

BRONZE_CKPT  = f'{BASE_PATH}/checkpoints/al_bronze'
SILVER_CKPT  = f'{BASE_PATH}/checkpoints/al_silver'
GOLD_CKPT    = f'{BASE_PATH}/checkpoints/al_gold'
