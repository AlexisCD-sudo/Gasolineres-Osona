#!/usr/bin/env python3
"""Descarrega els preus de tota Espanya del Ministeri i desa data.json en format compacte."""
import json
import ssl
import subprocess
import time
import urllib.request

API = ("https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/"
       "PreciosCarburantes/EstacionesTerrestres/")

FUELS = [
    "Precio Gasolina 95 E5",
    "Precio Gasolina 98 E5",
    "Precio Gasoleo A",
    "Precio Gasoleo Premium",
]


def num(v):
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def fetch():
    ctx = ssl.create_default_context()
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    except ssl.SSLError:
        pass
    req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
                return json.loads(r.read().decode("utf-8-sig"))
        except Exception as ex:
            print("urllib intent", attempt + 1, "ha fallat:", ex)
        try:
            out = subprocess.run(
                ["curl", "-sS", "--fail", "--tlsv1.2", "-A", "Mozilla/5.0", "-m", "120", API],
                capture_output=True, check=True)
            return json.loads(out.stdout.decode("utf-8-sig"))
        except Exception as ex:
            print("curl intent", attempt + 1, "ha fallat:", ex)
        time.sleep(10 * (attempt + 1))
    raise SystemExit("No s'ha pogut descarregar l'API del Ministeri")


def main():
    raw = fetch()
    provincies = []
    estacions = []
    for e in raw.get("ListaEESSPrecio", []):
        lat = num(e.get("Latitud"))
        lon = num(e.get("Longitud (WGS84)"))
        if lat is None or lon is None:
            continue
        prov = (e.get("Provincia") or "").title()
        if prov not in provincies:
            provincies.append(prov)
        estacions.append([
            (e.get("Rótulo") or "").title(),
            (e.get("Dirección") or "").title(),
            (e.get("Municipio") or "").title(),
            provincies.index(prov),
            e.get("Horario") or "",
            round(lat, 5),
            round(lon, 5),
        ] + [num(e.get(f)) for f in FUELS])
    # índex de província ordenat alfabèticament per al desplegable
    ordre = sorted(range(len(provincies)), key=lambda i: provincies[i])
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"actualitzat": raw.get("Fecha"), "provincies": provincies,
                   "ordre": ordre, "e": estacions},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(len(estacions), "gasolineres desades")


if __name__ == "__main__":
    main()
