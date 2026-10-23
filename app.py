import os
import json
import re
from datetime import datetime, timezone

import requests
import pandas as pd
from flask import Flask, jsonify

app = Flask(__name__)

def extraer_datos():
    """Consume la API pública de CoinGecko para obtener precios de criptomonedas."""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 10,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h"
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "datos": []}

def preprocesar(datos_crudos):
    """Limpia y normaliza los datos extraídos."""
    if not datos_crudos or isinstance(datos_crudos, dict):
        return pd.DataFrame()

    df = pd.DataFrame(datos_crudos)

    columnas = ["id", "symbol", "name", "current_price",
                "market_cap", "price_change_percentage_24h"]
    columnas_existentes = [c for c in columnas if c in df.columns]
    df = df[columnas_existentes].copy()

    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    if "name" in df.columns:
        # Remover caracteres especiales del nombre (solo letras, números y espacios)
        df["name"] = df["name"].astype(str).apply(
            lambda x: re.sub(r"[^a-zA-Z0-9\s]", "", x).strip()
        )

    for col in ["current_price", "market_cap", "price_change_percentage_24h"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df

def clasificar(df):
    """Asigna una etiqueta según el precio y la variación de 24h."""
    if df.empty:
        return df

    def etiqueta_precio(precio):
        if precio >= 10000:
            return "ALTO"
        elif precio >= 1000:
            return "MEDIO"
        elif precio > 0:
            return "BAJO"
        else:
            return "SIN_DATO"

    def etiqueta_variacion(var):
        if var >= 5:
            return "SUBE_FUERTE"
        elif var >= 0:
            return "SUBE"
        elif var >= -5:
            return "BAJA"
        else:
            return "BAJA_FUERTE"

    df["etiqueta_precio"] = df["current_price"].apply(etiqueta_precio)
    df["etiqueta_tendencia"] = df["price_change_percentage_24h"].apply(etiqueta_variacion)
    return df

def construir_log(df):
    """Genera el JSON final con los resultados analíticos."""
    if df.empty:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fuente": "CoinGecko API",
            "error": "No se pudieron procesar datos",
            "registros": [],
            "resumen": {}
        }

    registros = df.to_dict(orient="records")

    resumen = {
        "total_registros": len(df),
        "distribucion_precio": df["etiqueta_precio"].value_counts().to_dict() if "etiqueta_precio" in df else {},
        "distribucion_tendencia": df["etiqueta_tendencia"].value_counts().to_dict() if "etiqueta_tendencia" in df else {},
        "precio_promedio": round(float(df["current_price"].mean()), 2) if "current_price" in df else 0,
        "variacion_promedio_24h": round(float(df["price_change_percentage_24h"].mean()), 2) if "price_change_percentage_24h" in df else 0
    }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fuente": "CoinGecko API",
        "registros": registros,
        "resumen": resumen
    }

@app.route("/")
def home():
    return jsonify({
        "servicio": "Pipeline de Minería de Datos - CoinGecko",
        "endpoints": {
            "/run": "Ejecuta el pipeline completo (extracción + preprocesamiento + clasificación)",
            "/health": "Verifica que el servicio está activo"
        }
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

@app.route("/run")
def run_pipeline():
    """Ejecuta todo el pipeline y devuelve el JSON consolidado."""
    # 1. Extracción
    datos_crudos = extraer_datos()

    # 2. Preprocesamiento
    df_limpio = preprocesar(datos_crudos)

    # 3. Clasificación
    df_clasificado = clasificar(df_limpio)

    # 4. Log JSON
    log_final = construir_log(df_clasificado)

    return jsonify(log_final)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)