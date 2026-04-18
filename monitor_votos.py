import requests
import json
import os
from datetime import datetime

RECEPTOR_URL = os.environ.get("RECEPTOR_URL", "")
SECRET_TOKEN = os.environ.get("SECRET_TOKEN", "")
JSON_FILE    = "datos_votos.json"

URL_CANDIDATOS = "https://onpe-needle.linderhassinger.dev/api/onpe/candidates"
URL_TOTALES    = "https://onpe-needle.linderhassinger.dev/api/onpe/totals"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def enviar_a_cpanel(historial):
    try:
        payload = json.dumps({
            "token": SECRET_TOKEN,
            "data":  historial
        }, ensure_ascii=False)
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
        res_c = requests.get(URL_CANDIDATOS, headers=HEADERS, timeout=15)
        res_c.raise_for_status()
        data_c = res_c.json()
        c = {cand['nombreAgrupacionPolitica']: cand for cand in data_c.get('data', [])}

        v_rla   = int(c.get("RENOVACION POPULAR",        {}).get("totalVotosValidos", 0))
        v_rs    = int(c.get("JUNTOS POR EL PERU",         {}).get("totalVotosValidos", 0))
        v_nieto = int(c.get("PARTIDO DEL BUEN GOBIERNO",  {}).get("totalVotosValidos", 0))

        res_t = requests.get(URL_TOTALES, headers=HEADERS, timeout=15)
        res_t.raise_for_status()
        data_t = res_t.json()
        d = data_t.get("data", {})

        contabilizadas = d.get("contabilizadas", 0)
        dif_actual     = abs(v_rla - v_rs)

        historial = []
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                try:    historial = json.load(f)
                except: historial = []

        if historial:
            ultimo             = historial[-1]
            mem_rla            = ultimo.get("rla", 0)
            mem_rs             = ultimo.get("rs", 0)
            mem_contabilizadas = ultimo.get("contabilizadas", 0)
            mem_dif_absoluta   = ultimo.get("dif_absoluta", 0)
        else:
            mem_rla = mem_rs = mem_contabilizadas = mem_dif_absoluta = 0

        hay_cambio = (v_rla != mem_rla or v_rs != mem_rs or contabilizadas != mem_contabilizadas)

        if not hay_cambio:
            print("[%s] Sin cambios." % datetime.now().strftime('%H:%M:%S'))
            return

        ranking = sorted(
            [{"id": "rs", "votos": v_rs}, {"id": "rla", "votos": v_rla}, {"id": "nieto", "votos": v_nieto}],
            key=lambda x: x['votos'], reverse=True
        )
        puestos = {item['id']: idx + 2 for idx, item in enumerate(ranking)}

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

        registro = {
            "hora":           datetime.now().strftime("%H:%M:%S"),
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
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(historial, f, indent=4, ensure_ascii=False)

        print("[%s] %s" % (registro['hora'], trend))
        enviar_a_cpanel(historial)

    except Exception as e:
        print("[ERROR] %s" % e)

if __name__ == "__main__":
    obtener_datos()
