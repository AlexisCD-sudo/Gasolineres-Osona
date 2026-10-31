#!/usr/bin/env python3
"""Descarrega els preus del Ministeri i desa data.json amb les gasolineres d'Osona."""
import json
import time
import unicodedata
import urllib.request

API = ("https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/"
       "PreciosCarburantes/EstacionesTerrestres/FiltroProvincia/08")

MUNICIPIS = [
    "Vic", "Manlleu", "Torello", "Centelles", "Tona", "Taradell", "Seva", "Gurb",
    "Calldetenes", "Folgueroles", "Roda de Ter", "L'Esquirol", "Santa Maria de Corco",
    "Sant Hipolit de Voltrega", "Sant Quirze de Besora", "Sant Julia de Vilatorta",
    "Les Masies de Voltrega", "Les Masies de Roda", "Sant Vicenc de Torello",
    "Santa Eulalia de Riuprimer", "Sant Pere de Torello", "Malla", "Montesquiu",
    "Muntanyola", "Orista", "Olost", "Perafita", "Sant Bartomeu del Grau",
    "Sant Marti de Centelles", "Santa Cecilia de Voltrega", "Sant Sadurni d'Osormort",
    "Sora", "Collsuspina", "Les Masies", "Cantonigros", "Sant Agusti de Lluces",
    "Lluca", "Espinelves", "Vilanova de Sau", "El Brull", "Balenya", "Prats de Lluces",
]

FUELS = {
    "gasolina95": "Precio Gasolina 95 E5",
    "gasolina98": "Precio Gasolina 98 E5",
    "diesel": "Precio Gasoleo A",
    "dieselplus": "Precio Gasoleo Premium",
}


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()


def num(v):
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def fetch():
    req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8-sig"))
        except Exception as ex:
            print("intent", attempt + 1, "ha fallat:", ex)
            time.sleep(10 * (attempt + 1))
    raise SystemExit("No s'ha pogut descarregar l'API del Ministeri")


def main():
    raw = fetch()
    munis = {norm(m) for m in MUNICIPIS}
    out = []
    for e in raw.get("ListaEESSPrecio", []):
        if norm(e.get("Municipio")) in munis or norm(e.get("Localidad")) in munis:
            out.append({
                "nom": e.get("Rótulo", "").title(),
                "adreca": e.get("Dirección", "").title(),
                "municipi": e.get("Municipio", "").title(),
                "horari": e.get("Horario", ""),
                "lat": num(e.get("Latitud")),
                "lon": num(e.get("Longitud (WGS84)")),
                "preus": {k: num(e.get(v)) for k, v in FUELS.items()},
            })
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"actualitzat": raw.get("Fecha"), "gasolineres": out}, f, ensure_ascii=False)
    print(len(out), "gasolineres d'Osona desades")


if __name__ == "__main__":
    main()
