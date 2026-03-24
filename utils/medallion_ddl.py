# Ejecutar una sola vez para registrar las rutas Delta como tablas SQL
spark.sql(f"""
    CREATE DATABASE IF NOT EXISTS medallion
""")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS medallion.bronze_cliente
    USING DELTA LOCATION '{BRONZE_PATH}'
""")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS medallion.silver_cliente
    USING DELTA LOCATION '{SILVER_PATH}'
""")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS medallion.gold_cliente_por_tipo
    USING DELTA LOCATION '{GOLD_PATH}/por_tipo'
""")
