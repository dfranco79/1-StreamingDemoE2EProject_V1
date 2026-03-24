import os, json, time, pyodbc, logging
from dotenv import load_dotenv
from azure.eventhub import EventHubProducerClient, EventData

load_dotenv()
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s')

SQL_CONN_STR = (
    f"DRIVER={os.getenv('SQL_DRIVER')};"
    f"SERVER={os.getenv('SQL_SERVER')};"
    f"DATABASE={os.getenv('SQL_DATABASE')};"
    f"UID={os.getenv('SQL_USER')};"
    f"PWD={os.getenv('SQL_PASSWORD')};"
    "Encrypt=yes;TrustServerCertificate=no;"
)
EH_CONN_STR = os.getenv('EH_CONNECTION_STRING')
EH_NAME     = os.getenv('EH_NAME')
CT_FILE     = './ct_version.txt'
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL_SECONDS', 15))

# ─── Persistir la versión CT ─────────────────────────────────────────────
def load_ct_version() -> int:
    if os.path.exists(CT_FILE):
        with open(CT_FILE) as f:
            return int(f.read().strip())
    # Primera ejecución: obtener versión actual y arrancar desde aquí
    with pyodbc.connect(SQL_CONN_STR) as conn:
        v = conn.execute('SELECT CHANGE_TRACKING_CURRENT_VERSION()').fetchone()[0]
    save_ct_version(v)
    log.info(f'Primera ejecucion. Versión CT inicial: {v}')
    return v

def save_ct_version(v: int):
    with open(CT_FILE, 'w') as f:
        f.write(str(v))

# ─── Consulta Change Tracking con JOIN a la tabla ─────────────────────────
# SYS_CHANGE_OPERATION: I = Insert, U = Update, D = Delete
CT_QUERY = """
    SELECT
        ct.SYS_CHANGE_VERSION      AS ct_version,
        ct.SYS_CHANGE_OPERATION    AS ct_operation,   -- I / U / D
        ct.SYS_CHANGE_COLUMNS      AS ct_columns,     -- mapa de columnas cambiadas
        c.id_cliente, c.nombre, c.apellido, c.tipo_cliente,
        c.ruc, c.email, c.estado,
        CONVERT(VARCHAR, c.fecha_alta, 23)        AS fecha_alta,
        c.pais_origen,
        CONVERT(VARCHAR(23), c.updated_at, 126)   AS updated_at
    FROM CHANGETABLE(CHANGES dbo.Cliente, ?) AS ct
    LEFT JOIN dbo.Cliente c ON c.id_cliente = ct.id_cliente
    ORDER BY ct.SYS_CHANGE_VERSION ASC
"""

def main():
    log.info('Iniciando productor Change Tracking.')
    producer = EventHubProducerClient.from_connection_string(
        conn_str=EH_CONN_STR, eventhub_name=EH_NAME,keep_alive=10
    )
    with producer:
        while True:
            ct_version = load_ct_version()
            try:
                with pyodbc.connect(SQL_CONN_STR) as conn:
                    cursor = conn.execute(CT_QUERY, ct_version)
                    cols = [c[0] for c in cursor.description]
                    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]

                if rows:
                    batch = producer.create_batch()
                    max_version = ct_version
                    for row in rows:
                        if row['ct_version'] > max_version:
                            max_version = row['ct_version']
                        # Para DELETE, el JOIN retorna NULL en columnas de cliente.
                        # Enviamos el evento con la operación para que Spark lo procese.
                        payload = json.dumps(row, ensure_ascii=False, default=str)
                        event = EventData(payload)
                        try:
                            batch.add(event)
                        except ValueError:
                            producer.send_batch(batch)
                            batch = producer.create_batch()
                            batch.add(event)
                    if len(batch) > 0:
                        producer.send_batch(batch)
                    save_ct_version(max_version)
                    log.info(f'Publicados {len(rows)} cambios. Nueva versión CT: {max_version}')
                else:
                    log.info(f'Sin cambios desde versión CT {ct_version}.')

            except Exception as e:
                log.error(f'Error CT: {e}', exc_info=True)
            time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    main()
