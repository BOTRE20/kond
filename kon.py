
import requests
import json
import csv
from bs4 import BeautifulSoup

# Pages Kondjigbalè
PAGE_URL = "https://kondjigbale.com/tg/pharmacies-garde"
API_URL = "https://kondjigbale.com/tg/pharmacies"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": PAGE_URL
})

# 1. Charger la page pour obtenir la session et le jeton CSRF
page = session.get(PAGE_URL, timeout=30)
page.raise_for_status()

soup_page = BeautifulSoup(page.text, "html.parser")
csrf = soup_page.find("meta", attrs={"name": "csrf-token"})

if not csrf:
    raise RuntimeError("Jeton CSRF introuvable sur la page.")

csrf_token = csrf.get("content")

# 2. Envoyer la requête POST
response = session.post(
    API_URL,
    data={
        "search": "",
        "_token": csrf_token
    },
    headers={"X-CSRF-TOKEN": csrf_token},
    timeout=30
)

response.raise_for_status()
data = response.json()

if data.get("empty") is True:
    print("Aucune pharmacie trouvée.")
    raise SystemExit

# 3. Analyser le HTML renvoyé par le serveur
soup = BeautifulSoup(data.get("html", ""), "html.parser")
pharmacies = []

for carte in soup.select("article.post"):
    titre = carte.select_one("h4 a")
    paragraphes = carte.select("p.card-text")
    lien = titre.get("href", "") if titre else ""

    image = carte.select_one("img")

    pharmacie = {
        "nom": titre.get_text(" ", strip=True) if titre else "",
        "adresse": (
            paragraphes[0].get_text(" ", strip=True)
            if len(paragraphes) >= 1 else ""
        ),
        "telephone": (
            paragraphes[1].get_text(" ", strip=True)
            if len(paragraphes) >= 2 else ""
        ),
        "url": lien,
        "image": image.get("src", "") if image else ""
    }

    if pharmacie["nom"]:
        pharmacies.append(pharmacie)

# 4. Sauvegarder en JSON
with open("pharmacies_garde.json", "w", encoding="utf-8") as fichier:
    json.dump(pharmacies, fichier, ensure_ascii=False, indent=2)

# 5. Sauvegarder en CSV
with open(
    "pharmacies_garde.csv",
    "w",
    encoding="utf-8-sig",
    newline=""
) as fichier:
    champs = ["nom", "adresse", "telephone", "url", "image"]
    writer = csv.DictWriter(fichier, fieldnames=champs)
    writer.writeheader()
    writer.writerows(pharmacies)

print(f"{len(pharmacies)} pharmacies extraites.")
print("Fichiers créés : pharmacies_garde.json et pharmacies_garde.csv")

for pharmacie in pharmacies[:50]:
    print(
        pharmacie["nom"],
        "|", pharmacie["adresse"],
        "|", pharmacie["telephone"]
    )
