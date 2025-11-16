# app.py
import os
import socket
import time
import threading
from datetime import datetime, timezone
from collections import deque
from flask import Flask, jsonify, render_template  # Importe render_template
from waitress import serve
import sys

app = Flask(__name__)

# -------- CONFIG --------
MERCADO_PAGO_HOST = "api.mercadopago.com"
BCB_SPI_HOST = "www.bcb.gov.br"

CHECK_INTERVAL_SECONDS = 60
TCP_TIMEOUT = 3.0

MAX_LOG_ENTRIES = 50
FAIL_TOLERANCE = 3   # só considera falha após 3 checagens consecutivas
WINDOW_SIZE = 10     # média móvel para latência (últimos N valores)

# -------- STATE (Simplificado) --------
_state_lock = threading.Lock()
_state = {
    "PIX": "Desconhecido",
    "updated_at": None,
    "failure_log": [],
    "latency_bcb": deque(maxlen=WINDOW_SIZE),
    "latency_mp": deque(maxlen=WINDOW_SIZE),  # Mantido para checagem interna
    "fail_bcb": 0,
    "fail_mp": 0
}

# -------- Helpers de rede --------


def dns_resolve(hostname):
    try:
        ips = socket.gethostbyname_ex(hostname)[2]
        return ips
    except Exception:
        return []


def tcp_connect(hostname, port=443, timeout=TCP_TIMEOUT):
    try:
        t0 = time.time()
        sock = socket.create_connection((hostname, port), timeout=timeout)
        dur = time.time() - t0
        sock.close()
        return True, dur
    except Exception:
        return False, None

# -------- Avaliação de latência (média móvel) --------


def avaliar_latencia(medias):
    if not medias:
        return "Desconhecido"
    media = sum(medias) / len(medias)
    if media < 2.5:
        return "OK"
    elif media <= 5.0:
        return "Lento"
    else:
        return "Oscilando"

# -------- Funções de checagem (apenas DNS + TCP) --------


def checar_bcb():
    ips = dns_resolve(BCB_SPI_HOST)
    if not ips:
        return None, None
    tcp_ok, dur = tcp_connect(BCB_SPI_HOST)
    if tcp_ok:
        return "OK", dur
    return None, None


def checar_mp():
    ips = dns_resolve(MERCADO_PAGO_HOST)
    if not ips:
        return None, None
    tcp_ok, dur = tcp_connect(MERCADO_PAGO_HOST)
    if tcp_ok:
        return "OK", dur
    return None, None

# -------- Lógica principal --------


def checar_e_atualizar():
    try:
        status_bcb, dur_bcb = checar_bcb()
        status_mp, dur_mp = checar_mp()  # Checado, mas não usado na decisão final

        with _state_lock:
            prev = _state["PIX"]

            # Atualiza contadores de falha e latências
            if dur_bcb is not None:
                _state["latency_bcb"].append(dur_bcb)
                _state["fail_bcb"] = 0
            else:
                _state["fail_bcb"] += 1

            if dur_mp is not None:
                _state["latency_mp"].append(dur_mp)
                _state["fail_mp"] = 0
            else:
                _state["fail_mp"] += 1

            # Estima estado via média móvel
            if len(_state["latency_bcb"]) > 0 and _state["fail_bcb"] == 0:
                est_bcb = avaliar_latencia(_state["latency_bcb"])
            else:
                est_bcb = "Oscilando" if _state["fail_bcb"] >= FAIL_TOLERANCE else "OK"

            # Decisão final (Baseada APENAS no BCB)
            final = est_bcb
            causa = "Banco Central" if final != "OK" else None

            # Registra histórico apenas quando sai de OK
            if prev == "OK" and final != "OK":
                now_iso = datetime.now(timezone.utc).isoformat()
                _state["failure_log"].append({
                    "timestamp": now_iso,
                    "service": causa,
                    "status": final
                })
                if len(_state["failure_log"]) > MAX_LOG_ENTRIES:
                    _state["failure_log"].pop(0)

            _state["PIX"] = final
            _state["updated_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        # Não vamos travar o timer por exceção imprevista
        with _state_lock:
            _state["PIX"] = "Desconhecido"
            _state["updated_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        # agenda próxima checagem
        threading.Timer(CHECK_INTERVAL_SECONDS, checar_e_atualizar).start()


# inicia a primeira checagem com curto delay
threading.Timer(2.0, checar_e_atualizar).start()

# -------- ROTAS --------


@app.route("/")
def home():
    # Renderiza o template a partir da pasta 'templates'
    return render_template("index.html")


@app.route("/status")
def status_api():
    with _state_lock:
        # API simplificada
        return jsonify({
            "PIX": _state["PIX"],
            "updated_at": _state["updated_at"]
        })


@app.route("/history")
def history_api():
    with _state_lock:
        return jsonify(list(_state["failure_log"]))


# -------- SERVIDOR --------
if __name__ == "__main__":
    HOST_BIND = "0.0.0.0"
    PORTA = 5001

    def obter_ip_local():
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"
        finally:
            if s:
                s.close()

    IP_LOCAL = obter_ip_local()
    print(f" * Running on http://{IP_LOCAL}:{PORTA}")

    # executa com waitress (produção)
    serve(app, host=HOST_BIND, port=PORTA)
