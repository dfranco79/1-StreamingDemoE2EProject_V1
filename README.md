# 1-StreamingDemoE2EProject_V1
<div align="center">

# 🌊 Azure Event Hubs · Streaming Medallion Architecture

**End-to-end real-time data pipeline: Azure SQL Server → Event Hubs → Delta Lake**

[![Azure](https://img.shields.io/badge/Azure-Event%20Hubs-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/event-hubs)
[![Databricks](https://img.shields.io/badge/Databricks-Delta%20Lake-FF3621?style=for-the-badge&logo=databricks&logoColor=white)](https://www.databricks.com)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![PySpark](https://img.shields.io/badge/PySpark-Structured%20Streaming-E25A1C?style=for-the-badge&logo=apachespark&logoColor=white)](https://spark.apache.org)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)

</div>

---

## 📖 Overview

Este proyecto implementa una arquitectura de ingesta de datos en **tiempo real** usando servicios nativos de Azure y Databricks. Los registros de clientes generados en **Azure SQL Server** son capturados, publicados en **Azure Event Hubs**, y procesados hacia un **Data Lakehouse** con arquitectura medallion (Bronze → Silver → Gold) usando tres estrategias de consumo.

> **Caso de uso:** Sincronización en tiempo real de una tabla de clientes OLTP hacia una capa analítica con calidad de datos, deduplicación y KPIs de negocio.

---

## 🏗️ Arquitectura General

```mermaid
flowchart LR
    subgraph SOURCE["🗄️ Fuente de Datos"]
        SQL[(Azure SQL Server\ndbo.Cliente)]
    end

    subgraph PRODUCER["⚙️ Capa Productora"]
        direction TB
        PA["Opción A\nPolling + Watermark\n(Python)"]
        PB["Opción B\nChange Tracking\n(Python)"]
        PC["Opción C\nADF Copy Activity\n(No-code)"]
    end

    subgraph HUB["📨 Azure Event Hubs"]
        EH["evh-cliente\n4 particiones\nSKU Standard"]
    end

    subgraph CONSUMERS["🔥 Consumidores Spark"]
        direction TB
        S1["Escenario 1\nSpark Structured\nStreaming"]
        S2["Escenario 2\nAuto Loader\ncloudFiles"]
        S3["Escenario 3\nDelta Live\nTables"]
    end

    subgraph MEDALLION["🏅 Delta Lakehouse · ADLS Gen2"]
        direction TB
        B[("🥉 Bronze\nRaw · append-only")]
        SL[("🥈 Silver\nClean · typed · dedup")]
        G[("🥇 Gold\nKPIs · aggregations")]
        B --> SL --> G
    end

    subgraph CONSUME["📊 Consumo"]
        PBI["Power BI\nDirect Lake"]
        API["REST API\nAnalytics"]
    end

    SQL --> PA & PB & PC
    PA & PB & PC --> EH
    EH --> S1 & S2 & S3
    S1 & S2 & S3 --> B
    G --> PBI & API
```

---

## 🔄 Flujo de Datos Detallado

```mermaid
sequenceDiagram
    participant SQL as 🗄️ Azure SQL Server
    participant PROD as ⚙️ Productor Python
    participant EH as 📨 Event Hubs
    participant SPARK as 🔥 Spark / DLT
    participant BRONZE as 🥉 Bronze Delta
    participant SILVER as 🥈 Silver Delta
    participant GOLD as 🥇 Gold Delta

    loop Cada 15-30 segundos
        PROD->>SQL: SELECT WHERE updated_at > watermark
        SQL-->>PROD: Rows nuevas / modificadas
        PROD->>EH: send_batch(EventData[])
        Note over PROD,EH: partition_key = id_cliente
    end

    loop Micro-batch (30s / 1min)
        EH-->>SPARK: readStream (body, metadata)
        SPARK->>BRONZE: append raw_payload + metadatos EH
    end

    loop Micro-batch (1min / 5min)
        BRONZE-->>SPARK: readStream Delta
        SPARK->>SPARK: parse JSON · cast · validate · dedup
        SPARK->>SILVER: MERGE (upsert por id_cliente)
    end

    loop Batch cada hora
        SILVER-->>SPARK: read Delta
        SPARK->>GOLD: overwrite KPIs (por tipo, por país)
    end
```

---

## 📁 Estructura del Repositorio

```
📦 azure-eventhubs-medallion/
│
├── 📂 docs/
│   └── EventHubs_Medallion_Streaming_Guide.docx   # Guía técnica completa
│
├── 📂 producer/                    # Capa productora (SQL Server → Event Hubs)
│   ├── producer_polling.py         # Opción A: Polling con watermark
│   ├── producer_change_tracking.py # Opción B: Change Tracking (CT)
│   ├── verify_events.py            # Script de verificación del hub
│   ├── .env.example                # Plantilla de variables de entorno
│   └── requirements.txt
│
├── 📂 sql/                         # Scripts DDL para Azure SQL Server
│   ├── 01_create_table_cliente.sql # Tabla dbo.Cliente + índice + trigger
│   ├── 02_enable_change_tracking.sql
│   └── 03_seed_data.sql            # Datos de prueba
│
├── 📂 scenario_1_structured_streaming/    # Escenario 1
│   ├── 00_config.py
│   ├── 01_bronze_streaming.py
│   ├── 02_silver_streaming.py
│   └── 03_gold_streaming.py
│
├── 📂 scenario_2_autoloader/              # Escenario 2
│   ├── 00_config.py
│   ├── 01_al_bronze_streaming.py
│   ├── 02_al_silver_merge.py
│   └── 03_al_gold_batch.py
│
├── 📂 scenario_3_dlt/                     # Escenario 3
│   └── pipeline_cliente_medallion.py      # Pipeline DLT completo (3 capas)
│
├── 📂 adf/                                # Opción C: Azure Data Factory
│   ├── linkedService_AzureSQL.json
│   ├── linkedService_EventHubs.json
│   └── pipeline_SQLtoEventHubs.json
│
├── 📂 infra/                              # Infraestructura como código
│   └── deploy.sh                          # Script de creación de recursos Azure CLI
│
├── .gitignore
└── README.md
```

---

## ⚡ Comparativa de Escenarios

| Criterio | 🔵 Escenario 1<br>Structured Streaming | 🟣 Escenario 2<br>Auto Loader | 🟢 Escenario 3<br>Delta Live Tables |
|---|:---:|:---:|:---:|
| **Latencia** | < 30 seg | 5-10 min | < 30 seg (Continuous) |
| **Origen directo** | Event Hubs | Archivos ADLS (Capture) | Event Hubs |
| **Deduplicación** | Manual (foreachBatch) | Manual (MERGE) | Automática |
| **Calidad de datos** | Manual (filter/when) | Manual | Declarativa (`@expect`) |
| **Linaje automático** | ❌ | ❌ | ✅ Unity Catalog |
| **Reintentos auto** | ❌ Job retry | ❌ Job retry | ✅ |
| **Plataforma** | Databricks + Fabric | Databricks + Fabric | Solo Databricks |
| **Complejidad setup** | 🟡 Media | 🔴 Alta | 🟢 Baja |
| **Recomendado para** | POC / Fabric | Alto volumen de archivos | Producción Databricks |

---

## 🚀 Quick Start

### 1. Clonar el repositorio

```bash
git clone https://github.com/<tu-usuario>/azure-eventhubs-medallion.git
cd azure-eventhubs-medallion
```

### 2. Configurar variables de entorno

```bash
cp producer/.env.example producer/.env
# Editar producer/.env con tus credenciales
```

```ini
# producer/.env
SQL_SERVER=<tu-servidor>.database.windows.net
SQL_DATABASE=<tu-base-de-datos>
SQL_USER=productor_svc@<tu-servidor>
SQL_PASSWORD=<tu-password>
SQL_DRIVER={ODBC Driver 18 for SQL Server}

EH_CONNECTION_STRING=Endpoint=sb://<namespace>.servicebus.windows.net/;SharedAccessKeyName=producer-send;SharedAccessKey=<key>
EH_NAME=evh-cliente

POLL_INTERVAL_SECONDS=30
BATCH_SIZE=500
```

### 3. Preparar Azure SQL Server

```bash
# Ejecutar en SQL Server Management Studio o Azure Data Studio
sqlcmd -S <servidor>.database.windows.net -d <database> -U <user> -P <password> \
       -i sql/01_create_table_cliente.sql
sqlcmd -S <servidor>.database.windows.net -d <database> -U <user> -P <password> \
       -i sql/03_seed_data.sql
```

### 4. Instalar dependencias del productor

```bash
pip install -r producer/requirements.txt
```

### 5. Levantar el productor

```bash
# Opción A — Polling
python producer/producer_polling.py

# Opción B — Change Tracking (requiere CT habilitado en SQL)
python producer/producer_change_tracking.py
```

### 6. Verificar eventos en Event Hubs

```bash
python producer/verify_events.py
# Deberías ver JSON de clientes impresos en consola
```

### 7. Ejecutar el consumidor Spark (Databricks)

Importa los notebooks de la carpeta del escenario elegido en tu workspace de Databricks y ejecútalos en orden (00 → 01 → 02 → 03).

---

## 🛠️ Infraestructura Azure (CLI)

```bash
# Crear todos los recursos necesarios con Azure CLI
bash infra/deploy.sh

# O manualmente:
RESOURCE_GROUP="rg-streaming-poc"
LOCATION="eastus2"
NAMESPACE="evhns-streaming-poc"

az group create --name $RESOURCE_GROUP --location $LOCATION

az eventhubs namespace create \
  --name $NAMESPACE \
  --resource-group $RESOURCE_GROUP \
  --sku Standard \
  --enable-auto-inflate true \
  --maximum-throughput-units 10

az eventhubs eventhub create \
  --name evh-cliente \
  --namespace-name $NAMESPACE \
  --resource-group $RESOURCE_GROUP \
  --partition-count 4 \
  --message-retention 1

az eventhubs eventhub consumer-group create \
  --name cg-spark-structured \
  --eventhub-name evh-cliente \
  --namespace-name $NAMESPACE \
  --resource-group $RESOURCE_GROUP

az eventhubs eventhub consumer-group create \
  --name cg-dlt \
  --eventhub-name evh-cliente \
  --namespace-name $NAMESPACE \
  --resource-group $RESOURCE_GROUP
```

---

## 🏅 Arquitectura Medallion

```mermaid
flowchart TD
    subgraph BRONZE["🥉 Bronze — Raw Layer"]
        B1["raw_payload (string JSON)"]
        B2["eh_partition · eh_offset"]
        B3["eh_enqueued_time"]
        B4["ingestion_ts · source_system"]
    end

    subgraph SILVER["🥈 Silver — Curated Layer"]
        S1["id_cliente (PK, NOT NULL)"]
        S2["nombre · apellido · tipo_cliente"]
        S3["ruc · email (lowercase)"]
        S4["estado · fecha_alta (DATE)"]
        S5["pais_origen · email_valido (bool)"]
        S6["anio · mes (partición física)"]
    end

    subgraph GOLD["🥇 Gold — Business Layer"]
        G1["gold_cliente_por_tipo\nventana 1h · tipo · estado · total"]
        G2["gold_cliente_por_pais\nventana 1h · país · tasa_activos"]
        G3["gold_altas_mensual\naltas por año-mes · tipo"]
    end

    BRONZE -->|"parse JSON\ncast tipos\nvalidar email\ndedup MERGE"| SILVER
    SILVER -->|"watermark 10min\nventana 1h\naggregations"| GOLD

    style BRONZE fill:#CD7F32,color:#fff,stroke:#8B4513
    style SILVER fill:#C0C0C0,color:#222,stroke:#808080
    style GOLD   fill:#FFD700,color:#222,stroke:#B8860B
```

---

## 📐 Modelo de Datos — Tabla Silver

```mermaid
erDiagram
    SILVER_CLIENTE {
        string id_cliente PK
        string nombre
        string apellido
        string tipo_cliente
        string ruc
        string email
        int    estado
        date   fecha_alta
        string pais_origen
        bool   email_valido
        ts     eh_enqueued_time
        ts     silver_ts
        int    anio
        int    mes
    }

    GOLD_POR_TIPO {
        ts     window_start PK
        ts     window_end
        string tipo_cliente PK
        int    estado PK
        long   total_clientes
        long   clientes_unicos
        long   con_email_valido
        ts     gold_ts
    }

    GOLD_POR_PAIS {
        ts     window_start PK
        ts     window_end
        string pais_origen PK
        long   total_clientes
        double tasa_activos
    }

    SILVER_CLIENTE ||--o{ GOLD_POR_TIPO : "agrega por tipo"
    SILVER_CLIENTE ||--o{ GOLD_POR_PAIS : "agrega por país"
```

---

## 🔐 Seguridad

```mermaid
flowchart LR
    subgraph SECRETS["🔑 Gestión de Secretos"]
        KV["Azure Key Vault"]
        DS["Databricks Secrets"]
    end

    subgraph IDENTITIES["👤 Identidades de Servicio"]
        PROD_USR["productor_svc\nSQL Server\n(solo SELECT)"]
        SAS["SAS Policy\nproducer-send\n(solo Send)"]
        LISTEN["SAS Policy\nspark-listen\n(solo Listen)"]
    end

    KV -->|"secreto referenciado"| DS
    PROD_USR -->|"autenticación SQL"| DB[(Azure SQL)]
    SAS -->|"publicar eventos"| EH[Event Hubs]
    LISTEN -->|"consumir eventos"| EH
    DS -->|"dbutils.secrets.get()"| SPARK[Spark / DLT]
```

> ⚠️ **Nunca** commitees credenciales al repositorio. Usa siempre `.env` (ignorado por `.gitignore`) o Databricks Secrets en producción.

---

## 📦 Dependencias

### Productor Python

```
azure-eventhub>=5.11.0
pyodbc>=4.0.39
python-dotenv>=1.0.0
azure-identity>=1.15.0
```

### Clúster Databricks (Maven)

```
com.microsoft.azure:azure-eventhubs-spark_2.12:2.3.22
```

### Runtime Databricks recomendado

| Escenario | Runtime mínimo |
|---|---|
| Structured Streaming | DBR 11.3 LTS (Spark 3.3) |
| Auto Loader | DBR 10.4 LTS (Spark 3.2) |
| Delta Live Tables | DBR 12.2 LTS+ |

---

## 📚 Documentación Adicional

- 📄 [`docs/EventHubs_Medallion_Streaming_Guide.docx`](docs/EventHubs_Medallion_Streaming_Guide.docx) — Guía técnica completa con todos los pasos de configuración
- [Azure Event Hubs Documentation](https://learn.microsoft.com/azure/event-hubs/)
- [Databricks Auto Loader](https://docs.databricks.com/ingestion/auto-loader/index.html)
- [Delta Live Tables](https://docs.databricks.com/delta-live-tables/index.html)
- [Azure SQL Change Tracking](https://learn.microsoft.com/sql/relational-databases/track-changes/about-change-tracking-sql-server)

---

## 🗺️ Roadmap

- [x] Productor Python con Polling (Opción A)
- [x] Productor Python con Change Tracking (Opción B)
- [x] ADF Pipeline como productor (Opción C)
- [x] Escenario 1: Spark Structured Streaming
- [x] Escenario 2: Auto Loader + MERGE upsert
- [x] Escenario 3: Delta Live Tables con expectativas
- [ ] Terraform para infraestructura completa
- [ ] CI/CD con GitHub Actions para deploy de notebooks
- [ ] Monitoreo con Azure Monitor + alertas
- [ ] Soporte para Microsoft Fabric (Lakehouse + Eventstream)

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor abre un issue o pull request para:
- Correcciones de código o documentación
- Nuevos escenarios de consumo
- Soporte para otros orígenes de datos (Oracle, PostgreSQL, SAP)

---

## 📝 Licencia

MIT © 2025 — Distribuido con fines educativos y de referencia técnica.

---

<div align="center">

**Construido con ❤️ usando Azure Event Hubs · Apache Spark · Delta Lake**

</div>
