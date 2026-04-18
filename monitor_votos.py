# -*- coding: utf-8 -*-
import requests
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_PERU = ZoneInfo("America/Lima")
def ahora(): return datetime.now(TZ_PERU)

RECEPTOR_URL = os.environ.get("RECEPTOR_URL", "")
SECRET_TOKEN = os.environ.get("SECRET_TOKEN", "")

# URL pública del JSON en cPanel (para leer el historial)
JSON_URL = os.environ.get("JSON_URL", "")

URL_CANDIDATOS = "https://onpe-needle.linderhassinger.dev/api/onpe/candidates"
URL_TOTALES    = "https://onpe-needle.linderhassinger.dev/api/onpe/totals"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def leer_historial_cpanel():
    """Lee el historial actual desde el JSON público en cPanel."""
    try:
        resp = requests.get(JSON_URL + "?t=" + str(ahora().timestamp()), timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                print("  -> Historial leído: %d registros" % len(data))
                return data
    except Exception as e:
        print("  -> No se pudo leer historial: %s" % e)
    return []

def enviar_a_cpanel(historial):
    try:
        payload = json.dumps({"token": SECRET_TOKEN, "data": historial}, ensure_ascii=False)
        resp = requests.post(
            RECEPTOR_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        if resp.status_code == 200:
            print("  -> Enviado a cPanel OK: %s" % resp.text)
        else:
            print("  -> Error cPanel: %s %s" % (resp.status_code, resp.text[:200]))
    except Exception as e:
        print("  -> Fallo envio cPanel: %s" % e)

def obtener_datos():
    try:
        # 1. Votos por candidato
        res_c = requests.get(URL_CANDIDATOS, headers=HEADERS, timeout=15)
        res_c.raise_for_status()
        data_c = res_c.json()
        c = {}
        for cand in data_c.get('data', []):
            c[cand.get('nombreAgrupacionPolitica', '')] = cand

        v_rla = v_rs = v_nieto = 0
        for nombre, cand in c.items():
            if 'RENOVACI' in nombre:
                v_rla   = int(cand.get("totalVotosValidos", 0))
            if 'JUNTOS' in nombre:
                v_rs    = int(cand.get("totalVotosValidos", 0))
            if 'BUEN GOBIERNO' in nombre:
                v_nieto = int(cand.get("totalVotosValidos", 0))

        print("Votos - RLA: %d | RS: %d | Nieto: %d" % (v_rla, v_rs, v_nieto))

        # 2. Totales
        res_t = requests.get(URL_TOTALES, headers=HEADERS, timeout=15)
        res_t.raise_for_status()
        d = res_t.json().get("data", {})
        contabilizadas = d.get("contabilizadas", 0)
        dif_actual     = abs(v_rla - v_rs)

        # 3. Leer historial desde cPanel (la memoria real)
        historial = leer_historial_cpanel()

        if historial:
            ultimo             = historial[-1]
            mem_rla            = ultimo.get("rla", 0)
            mem_rs             = ultimo.get("rs", 0)
            mem_contabilizadas = ultimo.get("contabilizadas", 0)
            mem_dif_absoluta   = ultimo.get("dif_absoluta", 0)
        else:
            mem_rla = mem_rs = mem_contabilizadas = mem_dif_absoluta = 0

        # 4. Hay cambios?
        hay_cambio = (v_rla != mem_rla or v_rs != mem_rs or contabilizadas != mem_contabilizadas)

        if not hay_cambio:
            print("[%s] Sin cambios." % ahora().strftime('%H:%M:%S'))
            return

        # 5. Puestos
        ranking = sorted(
            [{"id":"rs","votos":v_rs},{"id":"rla","votos":v_rla},{"id":"nieto","votos":v_nieto}],
            key=lambda x: x['votos'], reverse=True
        )
        puestos = {item['id']: idx + 2 for idx, item in enumerate(ranking)}

        # 6. Trend
        cambio_brecha = mem_dif_absoluta - dif_actual
        lider = "RLA" if v_rla > v_rs else "SANCHEZ"

        if mem_dif_absoluta == 0:
            trend = "INICIO DE CONTEO"
        elif cambio_brecha > 0:
            quien_acorta = "RLA" if lider == "SANCHEZ" else "SANCHEZ"
            trend = "%s RECORTA %s VOTOS" % (quien_acorta, format(abs(cambio_brecha), ','))
        elif cambio_brecha < 0:
            trend = "%s AMPLIA VENTAJA (+%s)" % (lider, format(abs(cambio_brecha), ','))
        else:
            trend = "SIN CAMBIOS EN LA BRECHA"

        # 7. Nuevo registro
        registro = {
            "hora":           ahora().strftime("%H:%M:%S"),
            "rla":            v_rla,   "puesto_rla":   puestos['rla'],
            "rs":             v_rs,    "puesto_rs":    puestos['rs'],
            "nieto":          v_nieto, "puesto_nieto": puestos['nieto'],
            "dif_absoluta":   dif_actual,
            "trend":          trend,
            "avance":         d.get("actasContabilizadas", "0.000"),
            "totalActas":     d.get("totalActas", 0),
            "contabilizadas": contabilizadas,
            "enviadasJee":    d.get("enviadasJee", 0),
            "pendientesJee":  d.get("pendientesJee", 0)
        }

        historial.append(registro)
        print("[%s] %s" % (registro['hora'], trend))

        # 8. Enviar historial completo a cPanel
        enviar_a_cpanel(historial)

    except Exception as e:
        import traceback
        print("[ERROR] %s" % e)
        traceback.print_exc()

if __name__ == "__main__":
    obtener_datos()
