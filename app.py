import os
import math
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
ORIGIN_ADDRESS = os.getenv("ORIGIN_ADDRESS", "Avenida Melvin Jones, 333, Ponta Grossa, PR")
FRETE_API_TOKEN = os.getenv("FRETE_API_TOKEN", "123456")


def check_auth():
    token_recebido = request.headers.get("Authorization", "")
    token_esperado = f"Bearer {FRETE_API_TOKEN}"
    return token_recebido == token_esperado


def montar_destino(data):
    address = data.get("address") or {}
    shipping_address = data.get("shipping_address") or {}
    customer_address = data.get("customer_address") or {}

    source = address or shipping_address or customer_address or data

    cep = source.get("zipcode") or source.get("zip_code") or source.get("cep")
    rua = source.get("street") or source.get("address") or source.get("logradouro") or ""
    numero = source.get("number") or source.get("numero") or ""
    bairro = source.get("neighborhood") or source.get("bairro") or ""
    cidade = source.get("city") or source.get("cidade") or "Ponta Grossa"
    estado = source.get("state") or source.get("uf") or "PR"

    if cep:
        return f"{cep}, {cidade}, {estado}, Brasil"

    return f"{rua}, {numero}, {bairro}, {cidade}, {estado}, Brasil"


def calcular_distancia_km(destino):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"

    params = {
        "origins": ORIGIN_ADDRESS,
        "destinations": destino,
        "key": GOOGLE_MAPS_API_KEY,
        "language": "pt-BR",
        "region": "br",
        "units": "metric",
        "mode": "driving"
    }

    resposta = requests.get(url, params=params, timeout=10)
    resposta.raise_for_status()

    dados = resposta.json()

    if dados.get("status") != "OK":
        raise Exception(f"Erro Google Maps: {dados.get('status')}")

    elemento = dados["rows"][0]["elements"][0]

    if elemento.get("status") != "OK":
        raise Exception(f"Destino inválido: {elemento.get('status')}")

    metros = elemento["distance"]["value"]
    return metros / 1000


def calcular_preco_frete(distancia_km):
    if distancia_km > 30:
        return None

    if distancia_km <= 2:
        return 525

    if distancia_km <= 3:
        return 650

    km_extra = math.ceil(distancia_km - 3)
    return 650 + (km_extra * 150)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "servico": "API de Frete Yampi",
        "rota_frete": "/frete",
        "porta_local": 5002,
        "origem": ORIGIN_ADDRESS
    })


@app.route("/frete", methods=["GET"])
def frete_get():
    return jsonify({
        "status": "rota encontrada",
        "mensagem": "Esta rota funciona com POST. Use a Yampi ou curl para testar.",
        "exemplo": {
            "cep": "84010000",
            "city": "Ponta Grossa",
            "state": "PR"
        }
    })


@app.route("/frete", methods=["POST"])
def frete():
    try:
        if not check_auth():
            return jsonify({
                "error": "Unauthorized",
                "mensagem": "Token inválido. Confira o header Authorization."
            }), 401

        data = request.get_json(force=True, silent=True) or {}

        destino = montar_destino(data)

        if not destino.strip():
            return jsonify({
                "error": "Endereço de destino vazio"
            }), 400

        distancia_km = calcular_distancia_km(destino)
        preco = calcular_preco_frete(distancia_km)

        if preco is None:
            return jsonify([]), 200

        return jsonify([
            {
                "name": "Entrega Motoboy",
                "description": f"Entrega local - distância aproximada: {distancia_km:.1f} km",
                "price": int(preco),
                "delivery_time": 0
            }
        ]), 200

    except Exception as erro:
        print("ERRO:", erro)

        return jsonify({
            "error": "Erro ao calcular frete",
            "details": str(erro)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5002,
        debug=True
    )