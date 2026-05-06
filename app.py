import os
import math
import hmac
import base64
import hashlib
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
ORIGIN_ADDRESS = os.getenv("ORIGIN_ADDRESS", "Avenida Melvin Jones, 333, Ponta Grossa, PR")
FRETE_API_TOKEN = os.getenv("FRETE_API_TOKEN", "123456")
YAMPI_SECRET = os.getenv("YAMPI_SECRET", "")


def check_auth():
    # Aceita Authorization Bearer para nossos testes manuais
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {FRETE_API_TOKEN}":
        return True

    # Aceita assinatura oficial da Yampi, se você configurar YAMPI_SECRET
    if YAMPI_SECRET:
        received_signature = request.headers.get("X-Yampi-Hmac-SHA256", "")
        raw_body = request.get_data()

        local_signature = base64.b64encode(
            hmac.new(
                YAMPI_SECRET.encode("utf-8"),
                raw_body,
                hashlib.sha256
            ).digest()
        ).decode("utf-8")

        return hmac.compare_digest(local_signature, received_signature)

    return False


def montar_destino(data):
    cep = (
        data.get("zipcode")
        or data.get("zip_code")
        or data.get("cep")
    )

    if cep:
        return f"{cep}, Brasil"

    address = data.get("address") or {}
    shipping_address = data.get("shipping_address") or {}
    source = address or shipping_address or data

    rua = source.get("street") or source.get("address") or source.get("logradouro") or ""
    numero = source.get("number") or source.get("numero") or ""
    bairro = source.get("neighborhood") or source.get("bairro") or ""
    cidade = source.get("city") or source.get("cidade") or "Ponta Grossa"
    estado = source.get("state") or source.get("uf") or "PR"

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

    resposta = requests.get(url, params=params, timeout=3)
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
    """
    Retorna:
    - preco em reais
    - prazo em minutos

    Tabela:
    até 0.5 km = R$ 7,50 / 40 min
    até 1 km = R$ 8,00 / 40 min
    até 1.5 km = R$ 9,00 / 40 min
    até 2 km = R$ 10,50 / 45 min
    até 2.5 km = R$ 12,50 / 50 min
    até 3 km = R$ 13,50 / 55 min
    até 3.5 km = R$ 15,50 / 60 min
    até 4 km = R$ 16,00 / 65 min
    até 5 km = R$ 18,00 / 65 min
    até 6 km = R$ 20,00 / 70 min
    até 7 km = R$ 22,00 / 70 min
    até 10 km = R$ 27,00 / 70 min
    até 20 km = R$ 40,00 / 110 min
    """

    if distancia_km <= 0.5:
        return 7.50, 40

    if distancia_km <= 1:
        return 8.00, 40

    if distancia_km <= 1.5:
        return 9.00, 40

    if distancia_km <= 2:
        return 10.50, 45

    if distancia_km <= 2.5:
        return 12.50, 50

    if distancia_km <= 3:
        return 13.50, 55

    if distancia_km <= 3.5:
        return 15.50, 60

    if distancia_km <= 4:
        return 16.00, 65

    if distancia_km <= 5:
        return 18.00, 65

    if distancia_km <= 6:
        return 20.00, 70

    if distancia_km <= 7:
        return 22.00, 70

    if distancia_km <= 10:
        return 27.00, 70

    if distancia_km <= 20:
        return 40.00, 110

    return None, None


@app.route("/", methods=["GET", "POST"])
def home():
    return jsonify({
        "status": "online",
        "servico": "API de Frete Yampi",
        "rota_frete": "/frete",
        "origem": ORIGIN_ADDRESS
    })


@app.route("/frete", methods=["GET", "POST"])
def frete():
    try:
        if request.method == "GET":
            return jsonify({
                "status": "rota online",
                "mensagem": "Use POST para calcular o frete."
            })

        if not check_auth():
            return jsonify({
                "error": "Unauthorized",
                "mensagem": "Token ou assinatura inválida."
            }), 401

        data = request.get_json(force=True, silent=True) or {}

        destino = montar_destino(data)
        distancia_km = calcular_distancia_km(destino)
        preco, minutos = calcular_preco_frete(distancia_km)

        if preco is None or minutos is None:
            return jsonify({
                "quotes": []
            }), 200

        return jsonify({
            "quotes": [
                {
                    "name": f"Entrega Motoboy - até {minutos} min",
                    "service": "MOTOBOY",
                    "price": preco,
                    "days": 1,
                    "quote_id": 1,
                    "free_shipment": False
                }
            ]
        }), 200

    except Exception as erro:
        print("ERRO:", erro)

        return jsonify({
            "quotes": []
        }), 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5002,
        debug=True
    )