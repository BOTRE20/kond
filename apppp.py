
import os
import json
import requests
import streamlit as st

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import urljoin
from datetime import datetime

load_dotenv()

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PAGE_URL = "https://kondjigbale.com/tg/pharmacies-garde"
API_URL = "https://kondjigbale.com/tg/pharmacies"

API_KEY = os.getenv("DEEPINFRA_API_KEY")
MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct"
LLM_URL = "https://api.deepinfra.com/v1/openai/chat/completions"

st.set_page_config(
    page_title="Assistant Kondjigbalē",
    page_icon=" ", 
    layout="centered"
)


# --------------------------------------------------
# 1. RECUPERATION DES PHARMACIES
# --------------------------------------------------

def fetch_pharmacies():
    """Récupère les pharmacies depuis le site Kondjigbalē."""

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": PAGE_URL
        })

        # Charger la page pour obtenir la session et le CSRF
        page = session.get(PAGE_URL, timeout=30)
        page.raise_for_status()

        soup_page = BeautifulSoup(page.text, "html.parser")
        csrf = soup_page.find("meta", attrs={"name": "csrf-token"})

        if not csrf or not csrf.get("content"):
            raise RuntimeError(
                "Jeton CSRF introuvable. "
                "Vérifiez la page et le mécanisme d'authentification."
            )

        csrf_token = csrf["content"]

        # L'API accepte POST, pas GET
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
            return []

        html = data.get("html", "")

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        pharmacies = []

        for carte in soup.select("article.post"):
            titre = carte.select_one("h4 a")
            paragraphes = carte.select("p.card-text")
            image = carte.select_one("img")

            if not titre:
                continue

            lien = titre.get("href", "")
            image_url = image.get("src", "") if image else ""

            pharmacie = {
                "nom": titre.get_text(" ", strip=True),
                "adresse": (
                    paragraphes[0].get_text(" ", strip=True)
                    if len(paragraphes) > 0 else ""
                ),
                "telephone": (
                    paragraphes[1].get_text(" ", strip=True)
                    if len(paragraphes) > 1 else ""
                ),
                "url": urljoin(PAGE_URL, lien) if lien else "",
                "image": urljoin(PAGE_URL, image_url)
                if image_url else ""
            }

            if pharmacie["nom"]:
                pharmacies.append(pharmacie)

        return pharmacies


# --------------------------------------------------
# 2. CONSTRUCTION DU CONTEXTE POUR LE MODELE
# --------------------------------------------------

def build_pharmacy_context(pharmacies):
    """Transforme les résultats en contexte lisible par le LLM."""

    if not pharmacies:
        return (
            "Aucune pharmacie n'a été retournée par la source. "
            "Ne prétends pas qu'une pharmacie est de garde."
        )

    return json.dumps(
        pharmacies,
        ensure_ascii=False,
        indent=2
    )


# --------------------------------------------------
# 3. AGENT CONVERSATIONNEL
# --------------------------------------------------

def ask_agent(question, history, pharmacies):
    if not API_KEY:
        raise RuntimeError(
            "Clé DeepInfra absente. Configurez DEEPINFRA_API_KEY "
            "dans le fichier .env."
        )

    now = datetime.now().strftime("%d/%m/%Y à %H:%M")

    system_prompt = f"""
Tu es l'assistant conversationnel de Kondjigbalē,
une plateforme de santé numérique au Togo.

DATE ET HEURE DU SERVEUR :
{now}

MISSION :
Aider les utilisateurs à trouver des informations sur les
pharmacies de garde à partir des données fournies ci-dessous.

DONNEES RECUPEREES DEPUIS LE SITE :
{build_pharmacy_context(pharmacies)}

REGLES OBLIGATOIRES :
1. Utilise uniquement les données fournies pour citer les pharmacies.
2. Ne fabrique jamais de nom, d'adresse, de numéro ou d'horaire.
3. Une pharmacie présente dans les résultats n'est pas forcément
   confirmée comme étant de garde à l'heure actuelle.
4. Si les données ne précisent pas la date, la période de garde
   ou le statut actuel, explique cette limite à l'utilisateur.
5. Si aucune donnée n'est disponible, dis-le clairement et conseille
   de vérifier directement auprès de Kondjigbalē ou de la pharmacie.
6. Si l'utilisateur précise un quartier ou une ville, filtre les
   résultats uniquement lorsque les adresses permettent de le faire.
7. Présente les résultats de façon claire :
   nom, adresse, téléphone et lien si disponibles.
8. Réponds en français, de façon simple, naturelle et concise.
9. Si la question concerne une urgence médicale, recommande de
   contacter les services d'urgence appropriés. Ne remplace pas
   un professionnel de santé.
10. N'affirme jamais avoir vérifié un horaire ou une disponibilité
    si ces informations ne figurent pas dans les données.



Togo : KondjiGbalē connecte patients et médecins via ses plateformes web et mobile

Dans le but d’aider les populations de leur pays à disposer d’un carnet de santé numérique, trois jeunes togolais ont mis en place une application sur mesure.
KondjiGbalē est une solution healthtech développée par une jeune pousse togolaise. Elle permet aux utilisateurs de se mettre en relation avec les professionnels de la santé via ses plateformes web et mobile. La start-up, basée à Lomé, a été fondée en 2018 par trois jeunes togolais. Yvon Koudam, l’un des fondateurs, en est le président-directeur général.
« C’est d’abord un carnet de santé numérique, une sorte de passeport de santé. C'est ensuite une plateforme qui doit permettre au patient de bien gérer ses antécédents médicaux. Au médecin, il facilite le diagnostic et rend plus facile et rapide tout ce qui entre dans le processus de traitement d'un patient. La plateforme dispose de 4 canaux à savoir un site web, une application mobile, un centre d'appel en langues locales et un menu USSD. Les deux derniers sont destinés aux zones qui ne sont pas connectées ou sous couverture Internet », a indiqué Yvon Koudam.
L’application mobile est accessible uniquement sur Android. L’utilisateur, après téléchargement, devra s’inscrire en fournissant ses informations personnelles. Après cette étape, il pourra accéder aux divers services de la healthtech tels que le dossier médical partagé dans lequel on retrouve toutes les informations se rapportant à la santé de l’utilisateur ; la téléconsultation qui permet de prendre des rendez-vous en ligne et de faire une consultation avec des médecins en cas de problèmes de santé ; la commande et la livraison de médicaments en ligne ; les alertes pour la prise des médicaments et la pharmacie de garde. Cette dernière permet de géolocaliser et de prendre contact avec les pharmacies de garde les plus proches de la situation géographique de l’utilisateur.
La healthtech a reçu plusieurs récompenses depuis son lancement. En 2019, KondjiGbalē décroche les premiers prix au Pitch Your Startup Idea du Fenes et au Togo Innovation Challenge. L’application mobile a déjà été téléchargée plus d’un millier de fois, d’après les données de Play Store.

Il fonde KondjiGbale afin d’aider les médecins dans leur tâche qui est de sauver des vies. L’importance de sa start-up a été reconnue au Togo et à l’international et il a remporté plusieurs concours et représenté son pays dans plusieurs forums et sommets.
Le Togolais Yvon Koudam (photo) est un tech-entrepreneur titulaire d’un brevet de technicien supérieur (BTS) en programmation informatique obtenu en 2014 à l’institut polytechnique Defitech. Il cofonde en 2019 la start-up KondjiGbale, dont il est le président-directeur général, dans le but de faciliter l’accès aux soins de santé.
KondjiGbale est une start-up qui conçoit des solutions de technologie médicale afin de simplifier la gestion et le suivi quotidien de la santé des personnes. A travers sa plateforme, les patients ont accès à leur dossier médical qui peut être consulté par leur médecin, peuvent bénéficier d’un service de téléconsultation tous les jours de 6h à minuit et commander des médicaments en envoyant leur ordonnance.
La plateforme offre aussi la possibilité de trouver les pharmacies de garde et de programmer les moments de prise de médicament afin de recevoir des alertes aux heures indiquées. Ses services sont accessibles via une application mobile, une application web, un canal USSD, un centre d’appel en langues locales et un système de notification par SMS.
KondjiGbale est en partenariat avec trois centres de santé et plus de 34 professionnels de la santé. Elle a enregistré à ce jour plus de 5 165 patients et plus de 500 rendez-vous. En mars 2023, Yvon Koudam représente son pays au forum international de leadership des jeunes de Brazzaville (BILYF). Il a partagé son savoir et son expérience sur le panel : « Développement durable et économie numérique ».
Entre 2016 et 2022, l’entrepreneur a travaillé en tant qu’analyste programmeur dans la start-up Clin Sarl U au Togo. Il y a participé à la conception, la programmation et le développement d’applications pour des clients et entreprises telles que TMoney et AgriStore. Délégué de la semaine de l’innovation des jeunes au Togo, il a participé, en tant que speaker, au sommet Emerging Valley en décembre 2021.
Il a remporté pour son entreprise plusieurs concours, notamment le Pitch Your Startup Idea organisé par Enginnova et l’ambassade de France au Togo et le Togo Innovation Challenge du ministère du Développement à la base en 2019. Finaliste au concours Hacking Covid-19 Africa initié par HEC Paris en 2020, il a également fait partie des 10 finalistes du concours RFI App Challenge 5e édition en 2021.

"""

    messages = [{"role": "system", "content": system_prompt}]

    # Conserver les derniers échanges
    for item in history[-10:]:
        messages.append({
            "role": item["role"],
            "content": item["content"]
        })

    messages.append({
        "role": "user",
        "content": question
    })

    response = requests.post(
        LLM_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1200,
            "stream": False
        },
        timeout=90
    )

    response.raise_for_status()
    result = response.json()

    return result["choices"][0]["message"]["content"]


# --------------------------------------------------
# 4. INTERFACE CONVERSATIONNELLE
# --------------------------------------------------
st.markdown(
    '<h1 style="color: #008000;">Assistant IA Kondjigbalē</h1>',
    unsafe_allow_html=True
)

st.write(
    "Posez vos questions sur les pharmacies de garde "
    "et les informations disponibles."
)

st.caption(
    "Les informations de garde doivent être confirmées "
    "auprès de la pharmacie ou de Kondjigbalē."
)

if "history" not in st.session_state:
    st.session_state.history = []

# Afficher la conversation existante
for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input(
    "Ex. : Quelles pharmacies de garde à Lomé ?"
)

if question:
    st.session_state.history.append({
        "role": "user",
        "content": question
    })

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Recherche des pharmacies..."):
            try:
                # Récupérer des données récentes à chaque question
                pharmacies = fetch_pharmacies()

                answer = ask_agent(
                    question=question,
                    history=st.session_state.history[:-1],
                    pharmacies=pharmacies
                )

                st.markdown(answer)

                st.session_state.history.append({
                    "role": "assistant",
                    "content": answer
                })

            except requests.RequestException:
                st.error(
                    "Impossible de récupérer les informations "
                    "ou de contacter le service IA. "
                    "Veuillez réessayer plus tard."
                )

            except (RuntimeError, ValueError, KeyError, IndexError) as e:
                st.error(f"Erreur de configuration ou de réponse : {e}")

            except Exception:
                st.error(
                    "Une erreur inattendue est survenue. "
                    "Vérifiez les journaux du serveur."
                )

if st.button("Nouvelle conversation"):
    st.session_state.history = []
    st.rerun()
