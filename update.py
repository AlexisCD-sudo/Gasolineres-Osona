#!/usr/bin/env python3
"""Descarrega els preus de tota Espanya del Ministeri i desa data.json en format compacte.

Per a Catalunya afegeix també la comarca de cada gasolinera.
"""
import json
import math
import re
import ssl
import subprocess
import time
import unicodedata
import urllib.request

API = ("https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/"
       "PreciosCarburantes/EstacionesTerrestres/")
COMARQUES_URL = ("https://raw.githubusercontent.com/jorvixsky/geocatalunya/"
                 "main/comarques_municipis.json")

FUELS = [
    "Precio Gasolina 95 E5",
    "Precio Gasolina 98 E5",
    "Precio Gasoleo A",
    "Precio Gasoleo Premium",
]
PROV_CAT = {"barcelona", "girona", "gerona", "lleida", "lerida", "tarragona"}
MAX_KM_VEI = 15  # una gasolinera sense nom reconegut agafa la comarca de la més propera


def num(v):
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]", "", s)


def reordena(nom):
    """'Hospitalet de Llobregat (L')' o 'Hospitalet de Llobregat, L'' -> "L'Hospitalet de Llobregat"."""
    nom = (nom or "").strip()
    m = re.match(r"^(.*?)\s*\(\s*(els|les|el|la|l['’´]?)\s*\)$", nom, re.I)
    if not m:
        m = re.match(r"^(.*?),\s*(els|les|el|la|l['’´]?)$", nom, re.I)
    if not m:
        return nom
    base, art = m.group(1), m.group(2)
    return art + base if art[-1] in "'’´" else art + " " + base


def construeix_mapa(raw):
    """{'Vallès Oriental (41)': [{'city_name': 'Granollers', ...}]} -> {nom normalitzat: comarca}"""
    mapa = {}
    for clau, munis in raw.items():
        comarca = re.sub(r"\s*\(\d+\)\s*$", "", clau).strip()
        for m in munis:
            mapa[norm(reordena(m["city_name"]))] = comarca
    return mapa


def carrega_comarques():
    try:
        req = urllib.request.Request(COMARQUES_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            mapa = construeix_mapa(json.loads(r.read().decode("utf-8")))
        if len(mapa) < 500:
            raise ValueError("massa pocs municipis: %d" % len(mapa))
        return mapa
    except Exception as ex:
        print("Comarques no disponibles (es continua només amb províncies):", ex)
        return {}


def km(a, b, c, d):
    r = math.pi / 180
    x = math.sin((c - a) * r / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin((d - b) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def assigna_comarques(estacions, provincies, mapa):
    """Omple e[11] amb el nom de la comarca (o None). Retorna la llista de comarques."""
    if not mapa:
        return []
    cat = [e for e in estacions if norm(provincies[e[3]]) in PROV_CAT]
    for e in cat:
        e[11] = mapa.get(norm(reordena(e[2])))
    conegudes = [e for e in cat if e[11]]
    per_veinat = 0
    for e in cat:
        if e[11]:
            continue
        millor, dist = None, MAX_KM_VEI
        for o in conegudes:
            d = km(e[5], e[6], o[5], o[6])
            if d <= dist:
                millor, dist = o, d
        if millor:
            e[11] = millor[11]
            per_veinat += 1
    sense = sum(1 for e in cat if not e[11])
    print("Catalunya: %d gasolineres, %d per nom, %d per veïnatge, %d sense comarca"
          % (len(cat), len(conegudes), per_veinat, sense))
    return sorted({e[11] for e in cat if e[11]}, key=norm)


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
        ] + [num(e.get(f)) for f in FUELS] + [None])  # e[11] = comarca

    comarques = assigna_comarques(estacions, provincies, carrega_comarques())
    idx = {c: i for i, c in enumerate(comarques)}
    for e in estacions:
        e[11] = idx.get(e[11], -1)

    ordre = sorted(range(len(provincies)), key=lambda i: provincies[i])
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"actualitzat": raw.get("Fecha"), "provincies": provincies, "ordre": ordre,
                   "comarques": comarques, "e": estacions},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(len(estacions), "gasolineres desades,", len(comarques), "comarques")


if __name__ == "__main__":
    main()
