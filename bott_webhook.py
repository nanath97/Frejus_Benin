from core import bot, dp
from aiogram import types
import os
from datetime import datetime
from aiogram.dispatcher.handler import CancelHandler
import requests
from core import authorized_users
from detect_links_whitelist import lien_non_autorise
from collections import defaultdict
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ban_storage import ban_list
from middlewares.payment_filter import PaymentFilterMiddleware
from vip_topics import is_vip, get_user_id_by_topic_id, get_panel_message_id_by_user, update_vip_info, _user_topics


dp.middleware.setup(PaymentFilterMiddleware(authorized_users))






# map (chat_id, message_id) -> chat_id du client
pending_replies = {}


pending_notes = {}  # admin_id -> user_id

# Dictionnaire temporaire pour stocker les derniers messages de chaque client
last_messages = {}
# ADMIN / OWNER / ADMINS
ADMIN_ID = 7821620398  # propriétaire historique (conserve pour compatibilité)
OWNER_ID = ADMIN_ID
# ensemble des admins autorisés (modifie/add si besoin)
authorized_admin_ids = {7821620398, 8440217096}


def is_admin(user_id: int) -> bool:
    return user_id in authorized_admin_ids or user_id == OWNER_ID

# Constantes pour le bouton VIP et la vidéo de bienvenue (défaut)
VIP_URL = "https://buy.stripe.com/bJe6oG0Gp0wLbEF1rf7AI1H"
WELCOME_VIDEO_FILE_ID = "BAACAgQAAxkBAAMiaS7Oim3cdlPFoYDN1nQI0TKEmIUAAsohAALO7HlRcN1sBV_3-xo2BA"



pending_mass_message = {}
admin_modes = {}  # Clé = admin_id, Valeur = "en_attente_message"

# Mapping entre ID Telegram des admins et leur email dans Airtable 19juillet 2025 debut
ADMIN_EMAILS = {
    7821620398: "goddessbizagency@gmail.com",
}
# Mapping entre ID Telegram des admins et leur email dans Airtable 19juillet 2025 fin


# Paiements validés par Stripe, stockés temporairement
paiements_recents = defaultdict(list)  # ex : {14: [datetime1, datetime2]}

# ====== LIENS PAIEMENT GLOBALS (utilisés pour /env et pour l'envoi groupé payant) ======
liens_paiement = {
    "1": "https://buy.stripe.com/bJe6oG0Gp0wLbEF1rf7AI1H",
    "9": "https://buy.stripe.com/4gM3cucp7djx4cd3zn7AI1I",
    "14": "https://buy.stripe.com/14A8wOexf1AP2453zn7AI1g",
    "19": "https://buy.stripe.com/eVq00i9cVbbp101d9X7AI1J",
    "29": "https://buy.stripe.com/00w6oG1Ktcft9wx2vj7AI1K",
    "39": "https://buy.stripe.com/eVq6oGcp70wLeQR4Dr7AI1L",
    "49": "https://buy.stripe.com/eVq28q60J7Zd2455Hv7AI1M",
    "59": "https://buy.stripe.com/fZufZg2Ox4N13898TH7AI1N",
    "69": "https://buy.stripe.com/bJedR84WF4N12453zn7AI1O",
    "79": "https://buy.stripe.com/8x29AS60J3IX2459XL7AI1P",
    "89": "https://buy.stripe.com/8x2dR860J2ET389ee17AI1Q",
    "99": "https://buy.stripe.com/eVq00i9cV7Zd8st6Lz7AI1R",
    "109": "https://buy.stripe.com/8x2eVcgFn2ET5gh7PD7AI1S",
    "119": "https://buy.stripe.com/00wfZg3SBbbp2454Dr7AI1T",
    "129": "https://buy.stripe.com/fZu5kCdtbgvJaABfi57AI1U",
    "139": "https://buy.stripe.com/7sY7sK1KtgvJ2450nb7AI1V",
    "149": "https://buy.stripe.com/6oUdR80Gp0wL4cdc5T7AI1W",
    "159": "https://buy.stripe.com/dRmcN4cp793h101c5T7AI1X",
    "169": "https://buy.stripe.com/7sY5kCdtb7Zd8stgm97AI1Y",
    "179": "https://buy.stripe.com/fZueVcfBja7l6kl9XL7AI1Z",
    "189": "https://buy.stripe.com/eVq00iagZ93hcIJ4Dr7AI20",
    "199": "https://buy.stripe.com/7sYeVcgFn0wLeQRfi57AI21",
    "209": "https://buy.stripe.com/4gM9AS4WF93h1013zn7AI22",
    "500": "https://buy.stripe.com/4gMdR89cV2ET5gh2vj7AI23",
    "1000": "https://buy.stripe.com/eVqeVccp72ET7op3zn7AI24"
}


# 1.=== Variables globales ===
DEFAULT_FLOU_IMAGE_FILE_ID = "AgACAgQAAxkBAAMeaS7OAAEyjRvmckCs3618zJAULzX6AAJPC2sbzux5US0RTUEh8jQCAQADAgADeAADNgQ" # Remplace par le vrai file_id Telegram


# Fonction de détection de lien non autorisé
ALLOWED_DOMAINS = os.getenv("ALLOWED_DOMAINS", "").split(",")

# --- CONFIGURATION AIRTABLE ---
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("BASE_ID")
TABLE_NAME = os.getenv("TABLE_NAME")
SELLER_EMAIL = os.getenv("SELLER_EMAIL")  # ✅ ici


# ADMIN ID
ADMIN_ID = 7821620398 # 22
DIRECTEUR_ID = 7821620398  # ID personnel au ceo pour avertir des fraudeurs

# === MEDIA EN ATTENTE ===
contenus_en_attente = {}  # { user_id: {"file_id": ..., "type": ..., "caption": ...} }
paiements_en_attente_par_user = set()  # Set de user_id qui ont payé
# === FIN MEDIA EN ATTENTE ===

# === 221097 DEBUT

def initialize_authorized_users():
    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME.replace(' ', '%20')}"
        params = {"filterByFormula": "{Type acces}='VIP'"}
        headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        for record in data.get("records", []):
            telegram_id = record.get("fields", {}).get("ID Telegram")
            if telegram_id:
                try:
                    authorized_users.add(int(telegram_id))
                except ValueError:
                    print(f"[WARN] ID Telegram invalide : {telegram_id}")
        print(f"[INFO] {len(authorized_users)} utilisateurs VIP chargés depuis Airtable.")
    except Exception as e:
        print(f"[ERROR] Impossible de charger les VIP depuis Airtable : {e}")
# === 221097 FIN

# === Statistiques ===

# === Statistiques ===

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@dp.message_handler(commands=["stat"])
async def handle_stat(message: types.Message):
    admin_id = message.from_user.id
    email = ADMIN_EMAILS.get(admin_id)

    # Sécurité : on ne calcule des stats que pour un admin connu
    if not email:
        await bot.send_message(
            message.chat.id,
            "❌ Your admin email is not configured in the bot. Talk to Nova Pulse to update it."
        )
        return

    await bot.send_message(message.chat.id, "📥 Processing your current sales statistics...")

    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME.replace(' ', '%20')}"
        headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}"
        }

        # 🔑 On filtre uniquement les lignes qui appartiennent à CET admin
        params = {
            "filterByFormula": f"{{Email}} = '{email}'"
        }

        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        ventes_totales = 0.0
        ventes_jour = 0.0
        contenus_vendus = 0
        vip_ids = set()

        today = datetime.now().date().isoformat()
        mois_courant = datetime.now().strftime("%Y-%m")

        for record in data.get("records", []):
            fields = record.get("fields", {})

            user_id = fields.get("ID Telegram", "")
            type_acces = (fields.get("Type acces", "") or "").lower()
            date_str = fields.get("Date", "") or ""
            mois = fields.get("Mois", "") or ""

            try:
                montant = float(fields.get("Montant", 0) or 0)
            except Exception:
                montant = 0.0

            # 💶 Ventes du mois (on ignore les lignes VIP “0 $”)
            if mois == mois_courant and montant > 0 and type_acces != "vip":
                ventes_totales += montant

            # 📅 Ventes du jour + contenus vendus
            if date_str.startswith(today) and montant > 0 and type_acces != "vip":
                ventes_jour += montant
                contenus_vendus += 1

            # 🌟 Clients VIP = clients qui ont payé au moins une fois
            # (Type acces = "paiement" OU "vip") ET montant > 0
            if user_id and montant > 0 and type_acces in ("paiement", "vip"):
                vip_ids.add(user_id)

        clients_vip = len(vip_ids)
        benefice_net = round(ventes_totales * 0.88, 2)

        message_final = (
            f"📊 Your sales statistics :\n\n"
            f"💰 Today's sales : {ventes_jour}$\n"
            f"💶 Total sales : {ventes_totales}$\n"
            f"📦 Total content sold : {contenus_vendus}\n"
            f"🌟 Clients VIP : {clients_vip}\n"
            f"📈 Estimated net profit : {benefice_net}$\n\n"
            f"_The profit takes into account a 12% commission._"
        )

        vip_button = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📋 See my VIPs", callback_data="voir_mes_vips")
        )
        await bot.send_message(message.chat.id, message_final, parse_mode="Markdown", reply_markup=vip_button)

    except Exception as e:
        print(f"Erreur dans /stat : {e}")
        await bot.send_message(message.chat.id, "❌ An error occurred while retrieving statistics.")

import requests
from datetime import datetime

def get_vip_ids_for_admin_email(email: str):
    """
    Récupère les IDs Telegram des VIPs pour un admin donné,
    en utilisant la même logique que /stat.
    """
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME.replace(' ', '%20')}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }
    params = {
        "filterByFormula": f"{{Email}} = '{email}'"
    }

    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    vip_ids = set()

    for record in data.get("records", []):
        fields = record.get("fields", {})

        user_id = fields.get("ID Telegram", "")
        type_acces = (fields.get("Type acces", "") or "").lower()

        try:
            montant = float(fields.get("Montant", 0) or 0)
        except Exception:
            montant = 0.0

        # 🌟 VIP = client qui a payé au moins une fois (paiement ou vip) avec montant > 0
        if user_id and montant > 0 and type_acces in ("paiement", "vip"):
            vip_ids.add(user_id)

    return vip_ids


# DEBUT de la fonction du proprietaire ! Ne pas toucher

@dp.message_handler(commands=["nath"])
async def handle_nath_global_stats(message: types.Message):
    if message.from_user.id != int(ADMIN_ID):
        await bot.send_message(message.chat.id, "❌ Timal, tu n'as pas la permission d'utiliser ce bouton.")
        return

    await bot.send_message(message.chat.id, "🕓 Récupération des statistiques globales en cours...")

    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME.replace(' ', '%20')}"
        headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}"
        }

        response = requests.get(url, headers=headers)
        data = response.json()

        ventes_par_email = {}

        for record in data.get("records", []):
            fields = record.get("fields", {})
            email = fields.get("Email", "")
            montant = float(fields.get("Montant", 0))

            if not email:
                continue

            if email not in ventes_par_email:
                ventes_par_email[email] = 0
            ventes_par_email[email] += montant

        if not ventes_par_email:
            await bot.send_message(message.chat.id, "Aucune donnée trouvée dans Airtable.")
            return

        lignes = ["📊 *Récapitulatif global des ventes :*\n"]
        total_global = 0

        for email, total in ventes_par_email.items():
            benefice_vendeur = round(total * 0.88, 2)
            benefice_nath = round(total * 0.12, 2)
            total_global += total
            lignes.append(
                f"• {email} → {total:.2f} €  |  Vendeur : {benefice_vendeur:.2f} €  |  Toi (12 %) : {benefice_nath:.2f} $"
            )

        total_benefice_nath = round(total_global * 0.12, 2)
        total_benefice_vendeurs = round(total_global * 0.88, 2)

        lignes.append("\n💰 *Synthèse globale :*")
        lignes.append(f"• Total des ventes : {total_global:.2f} €")
        lignes.append(f"• Tes bénéfices (12 %) : {total_benefice_nath:.2f} €")
        lignes.append(f"• Bénéfices vendeurs (88 %) : {total_benefice_vendeurs:.2f} €")

        await bot.send_message(message.chat.id, "\n".join(lignes), parse_mode="Markdown")

    except Exception as e:
        print(f"Erreur dans /nath : {e}")
        await bot.send_message(message.chat.id, "❌ Une erreur est survenue lors du traitement des statistiques.")

# FIN de la fonction du propriétaire


# Liste des prix autorisés
prix_list = [1, 3, 9, 14, 19, 24, 29, 34, 39, 44, 49, 59, 69, 79, 89, 99, 109, 119, 129, 139, 149, 159, 169, 179, 189, 199, 209, 500, 1000]

# Liste blanche des liens autorisés
WHITELIST_LINKS = [
    "https://novapulseonline.wixsite.com/",
    "https://buy.stripe.com/",
    "https://t.me/mini_jessie_bot?start=cdan"
    "http://t.me/lunagiabot?start=cdan" # 22 Rajouter  le lien propre de l'admin
]


def lien_non_autorise(text):
    words = text.split()
    for word in words:
        if word.startswith("http://") or word.startswith("https://"):
            if not any(domain.strip() in word for domain in ALLOWED_DOMAINS):
                return True
    return False

@dp.message_handler(lambda message: (message.text and ("http://" in message.text or "https://" in message.text)) or (message.caption and ("http://" in message.caption or "https://" in message.caption)), content_types=types.ContentType.ANY)
async def verifier_les_liens_uniquement(message: types.Message):
    text_to_check = message.text or message.caption or ""
    if lien_non_autorise(text_to_check):
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            await bot.send_message(chat_id=message.chat.id, text="🚫 External links are prohibited.")
            
            # Message perso au CEO pour avertir des fraudeurs
            await bot.send_message(DIRECTEUR_ID,
                                   f"🚨 Tentative de lien interdit détectée !\n\n"
            f"👤 User: {message.from_user.username or message.from_user.first_name}\n"
            f"🆔 ID: {message.from_user.id}\n"
            f"🔗 Lien envoyé : {text_to_check}")

            print(f"🔴 Lien interdit supprimé : {text_to_check}")
        except Exception as e:
            print(f"Erreur lors de la suppression du lien interdit : {e}")
        raise CancelHandler()

# Fonction pour ajouter un paiement à Airtable 22 Changer l'adresse mail par celui de l'admin

def log_to_airtable(
    pseudo,
    user_id,
    type_acces,
    montant,
    contenu="Paiement Telegram",
    email="goddessbizagency@gmail.com",
):
    if not type_acces:
        type_acces = "Paiement"  # Par défaut pour éviter erreurs

    url_base = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME.replace(' ', '%20')}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    now = datetime.now()

    # Champs communs qu'on veut toujours écrire / mettre à jour
    fields = {
        "Pseudo Telegram": pseudo or "-",
        "ID Telegram": str(user_id),
        "Type acces": str(type_acces),
        "Montant": float(montant),
        "Contenu": contenu,
        "Email": email,
        "Date": now.isoformat(),
        "Mois": now.strftime("%Y-%m")
    }

    try:
        # 🔹 Cas particulier : accès VIP
        if str(type_acces).lower() == "vip":
            # On cherche la/les lignes VIP existantes pour ce user
            params = {
                "filterByFormula": f"AND({{ID Telegram}} = '{user_id}', {{Type acces}} = 'VIP')"
            }
            r = requests.get(url_base, headers=headers, params=params)
            r.raise_for_status()
            records = r.json().get("records", [])

            if records:
                # On choisit de préférence une ligne qui a déjà un Topic ID
                rec_to_update = records[0]
                for rec in records:
                    if rec.get("fields", {}).get("Topic ID"):
                        rec_to_update = rec
                        break

                rec_id = rec_to_update["id"]
                patch_url = f"{url_base}/{rec_id}"

                # ⚠️ Important : on n'envoie PAS "Topic ID" ici → Airtable le conserve tel quel
                data = {"fields": fields}
                response = requests.patch(patch_url, json=data, headers=headers)
            else:
                # Sécurité : si aucune ligne VIP n'existe (cas improbable),
                # on crée une nouvelle ligne comme avant
                data = {"fields": fields}
                response = requests.post(url_base, json=data, headers=headers)

        # 🔹 Tous les autres types d'accès (Paiement simple, groupé, etc.)
        else:
            data = {"fields": fields}
            response = requests.post(url_base, json=data, headers=headers)

        if response.status_code != 200:
            print(f"❌ Erreur Airtable : {response.text}")
        else:
            print("✅ Paiement ajouté dans Airtable avec succès !")

    except Exception as e:
        print(f"Erreur lors de l'envoi à Airtable : {e}")



# Création du clavier

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(
)
keyboard_admin = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard_admin.add(
    types.KeyboardButton("📖 Control"),
    types.KeyboardButton("📊 Statistics")
)

keyboard_admin.add(
    types.KeyboardButton("✉️ Message to all VIPs")
)

from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta

@dp.message_handler(commands=["start"])
async def handle_start(message: types.Message):
    user_id = message.from_user.id
    param = (message.get_args() or "").strip()

    # === Cas A : /start=cdanXX (paiement Stripe pour un contenu) ===
    if param.startswith("cdan") and param[4:].isdigit():
        montant = int(param[4:])
        if montant in prix_list:
            now = datetime.now()
            paiements_valides = [
                t for t in paiements_recents.get(montant, [])
                if now - t < timedelta(minutes=3)
            ]
            if not paiements_valides:
                await bot.send_message(
                    user_id,
                    "❌ Invalid payment ! Stripe declined your payment due to insufficient funds or a general decline. Please verify your payment capabilities.."
                )
                # avertir tous les admins
                for adm in authorized_admin_ids:
                    try:
                        await bot.send_message(
                            adm,
                            f"⚠️ Problem! Stripe declined your customer's payment. {message.from_user.username or message.from_user.first_name}."
                        )
                    except Exception:
                        pass
                return

            # Paiement validé
            paiements_recents[montant].remove(paiements_valides[0])
            authorized_users.add(user_id)

            # Si un contenu était en attente → on le livre
            if user_id in contenus_en_attente:
                contenu = contenus_en_attente[user_id]
                if contenu["type"] == types.ContentType.PHOTO:
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=contenu["file_id"],
                        caption=contenu.get("caption")
                    )
                elif contenu["type"] == types.ContentType.VIDEO:
                    await bot.send_video(
                        chat_id=user_id,
                        video=contenu["file_id"],
                        caption=contenu.get("caption")
                    )
                elif contenu["type"] == types.ContentType.DOCUMENT:
                    await bot.send_document(
                        chat_id=user_id,
                        document=contenu["file_id"],
                        caption=contenu.get("caption")
                    )
                del contenus_en_attente[user_id]
            else:
                # Le client a payé avant que tu aies /envXX → on note le paiement en attente
                paiements_en_attente_par_user.add(user_id)

            await bot.send_message(
                user_id,
                f"✅ Thank you for your payment of {montant}$ 💖 ! Here is your content...\n\n"
                f"_❗️If you have any concerns about your order, please contact us at novapulse.online@gmail.com_",
                parse_mode="Markdown"
            )
            # avertir tous les admins
            for adm in authorized_admin_ids:
                try:
                    await bot.send_message(
                        adm,
                        f"💰 New payment of {montant}$ to {message.from_user.username or message.from_user.first_name}."
                    )
                except Exception:
                    pass
            log_to_airtable(
                pseudo=message.from_user.username or message.from_user.first_name,
                user_id=user_id,
                type_acces="Paiement",
                montant=float(montant),
                contenu="Paiement validé via Stripe webhook + redirection"
            )
            try:
                from vip_topics import ensure_topic_for_vip
                topic_id = await ensure_topic_for_vip(message.from_user)
            except Exception:
                topic_id = None
            if topic_id is not None:
                try:
                    await bot.request(
                        "sendMessage",
                        {
                            "chat_id": int(os.getenv("STAFF_GROUP_ID", "0")),
                            "message_thread_id": topic_id,
                            "text": (
                                f"💰 *New payment content*\n\n"
                                f"👤 Client : @{message.from_user.username or message.from_user.first_name}\n"
                                f"💶 Montant : {montant} $\n"
                                f"📊 Payment recorded in statistics."
                            ),
                            "parse_mode": "Markdown"
                        }
                    )
                except Exception as e:
                    print(f"[VIP_TOPICS] Erreur envoi notif paiement contenu dans topic {topic_id} : {e}")

            return

        # 🔔 Notification dans le TOPIC du client (et plus dans le bot)
                 


        # === Cas B : /start=vipcdan (retour après paiement VIP) ===
    if param == "vipcdan":
        # 1) On marque le user comme VIP côté bot
        authorized_users.add(user_id)

        # 2) On crée / récupère le topic VIP pour ce client
        try:
            from vip_topics import ensure_topic_for_vip
            topic_id = await ensure_topic_for_vip(message.from_user)
        except Exception as e:
            # On log mais ON NE BLOQUE PAS l'envoi des médias
            print(f"[VIP] Erreur ensure_topic_for_vip pour {user_id}: {e}")
            topic_id = None  # pour éviter un NameError plus loin

        # 3) On envoie le pack VIP (2 photos + 1 vidéo)
        await bot.send_message(
            user_id,
            "✨ Bienvenue dans le VIP mon coeur 💕! Et voici ton cadeau 🎁:"
        )

        # 2 photos VIP
        await bot.send_photo(
            chat_id=user_id,
            photo="AgACAgQAAxkBAAPOaQoZ7sGjzKHvOp2HTWkdF85sPlgAArQLaxtek1FQMYkzf8-CaRABAAMCAAN5AAM2BA"
        )
        await bot.send_photo(
            chat_id=user_id,
            photo="AgACAgQAAxkBAAPIaQoZhWQxhphnbPASL7B0azRsfL4AArILaxtek1FQYk5K1KDLoegBAAMCAAN5AAM2BA"
        )

        # 1 vidéo VIP
        await bot.send_video(
            chat_id=user_id,
            video="BAACAgQAAxkBAAPGaQoZZD2d0lbeVGfu_rF9OI4g2M8AAtkaAAJek1FQLrBTrfP_5wg2BA"
        )

        # 4) Logs Airtable
        log_to_airtable(
            pseudo=message.from_user.username or message.from_user.first_name,
            user_id=user_id,
            type_acces="VIP",
            montant=1.0,
            contenu="Pack 2 photos + 1 vidéo + accès VIP"
        )

        # 5) Notification dans le TOPIC du client (si on a réussi à le récupérer)
        if topic_id is not None:
            try:
                await bot.request(
                    "sendMessage",
                    {
                        "chat_id": int(os.getenv("STAFF_GROUP_ID", "0")),
                        "message_thread_id": topic_id,
                        "text": (
                            f"🌟 *Nouveau VIP confirmé*\n\n"
                            f"👤 Client : @{message.from_user.username or message.from_user.first_name}\n"
                            f"💶 Montant : 1 $\n"
                            f"📊 Accès VIP enregistré dans le dashboard."
                        ),
                        "parse_mode": "Markdown"
                    }
                )
            except Exception as e:
                print(f"[VIP_TOPICS] Erreur envoi notif VIP dans topic {topic_id} : {e}")

        return  # on sort ici pour ne pas passer à l’accueil normal



    # === Cas C : /start simple (accueil normal) ===
    if is_admin(user_id):
        await bot.send_message(
            user_id,
            "👋 Hello admin! You can view the control list and check your statistics !",
            reply_markup=keyboard_admin
        )
        return

    await bot.send_message(
    user_id,
    "_🟢 Luna is online_",
    reply_markup=keyboard,
    parse_mode="Markdown"
)


    # 2) Vidéo de présentation + bouton VIP
    await bot.send_video(
    chat_id=user_id,
    video=WELCOME_VIDEO_FILE_ID
)


# TEST A SUPPRIMER DEBUT

@dp.message_handler(
    lambda m: m.chat.id == STAFF_GROUP_ID and m.from_user.id in pending_notes,
    content_types=[types.ContentType.TEXT]
)
async def handle_vip_note(message: types.Message):
    admin_id = message.from_user.id

    # DEBUG : tu verras ça dans Render si besoin
    print(f"[NOTES] handle_vip_note triggered for admin_id={admin_id}, chat_id={message.chat.id}")
    print(f"[NOTES] pending_notes = {pending_notes}")

    # Récupérer le VIP concerné et enlever le mode "note"
    vip_user_id = pending_notes.pop(admin_id, None)
    if not vip_user_id:
        # cas bizarre : on était censé être en mode note mais le dict est vide
        return

    note_text = (message.text or "").strip()
    if not note_text:
        await message.reply("❌ Empty note, nothing has been recorded.")
        raise CancelHandler()

    print(f"[NOTES] Note reçue pour VIP user_id={vip_user_id} par admin_id={admin_id} : {note_text}")

    # Mise à jour des infos VIP (NOTE UNIQUEMENT)
    info = update_vip_info(vip_user_id, note=note_text)

    panel_message_id = info.get("panel_message_id")
    admin_name = info.get("admin_name") or "Aucun"

    if not panel_message_id:
        await message.reply("⚠️ Unable to find the VIP panel for this customer.")
        raise CancelHandler()
    full_note = info.get("note", note_text)
    panel_text = (
        "🧐 VIP CONTROL PANEL\n\n"
        f"👤 Client : {vip_user_id}\n"
        f"📒 Notes : {full_note}\n"
        f"👤 Admin in charge : {admin_name}"
    )

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Take charge", callback_data=f"prendre_{vip_user_id}"),
        InlineKeyboardButton("📝 Add a note", callback_data=f"annoter_{vip_user_id}")
    )

    # On met à jour le panneau dans le STAFF_GROUP
    await bot.edit_message_text(
        chat_id=STAFF_GROUP_ID,
        message_id=panel_message_id,
        text=panel_text,
        reply_markup=kb
    )

    # Petite confirmation dans le topic
    await message.reply("✅ Note recorded and panel updated.", reply=False)

    # 🔥 Très important : empêche les autres handlers (dont /env) de traiter ce message
    raise CancelHandler()


# TEST A SUPPRIMER FIN


# Message et média personnel avec lien 

import re

@dp.message_handler(
    lambda message: is_admin(message.from_user.id)
    and admin_modes.get(message.from_user.id) is None   # ✅ Seulement si pas de diffusion en cours
    and (
        (message.text and "/env" in message.text.lower()) or 
        (message.caption and "/env" in message.caption.lower())
    ),
    content_types=[types.ContentType.TEXT, types.ContentType.PHOTO, 
                   types.ContentType.VIDEO, types.ContentType.DOCUMENT]
)
async def envoyer_contenu_payant(message: types.Message):
    import re  # au cas où pas importé en haut
    admin_id = message.from_user.id

    # 0) ⚠️ si on est en mode "envoi groupé payant", on NE FAIT RIEN
    if admin_modes.get(admin_id) == "en_attente_message_payant":
        return

    # 1) ici c'est le mode NORMAL : on veut répondre à UN client
    if not message.reply_to_message:
        await bot.send_message(
            chat_id=admin_id,
            text="❗ Use this command in response to a message from the client."
        )
        return

    # 2) retrouver le client ciblé
    if message.reply_to_message.forward_from:
        user_id = message.reply_to_message.forward_from.id
    else:
        user_id = pending_replies.get((message.chat.id, message.reply_to_message.message_id))

    # 🔥 CAS SPÉCIAL : si on n'a pas de user_id mais qu'on est en mode "note VIP"
    if not user_id:
        # si cet admin est en mode note, on utilise CE message comme note
        if admin_id in pending_notes:
            vip_user_id = pending_notes.pop(admin_id)
            note_text = (message.text or message.caption or "").strip()

            if not note_text:
                await bot.send_message(
                    chat_id=admin_id,
                    text="❗ Empty note, nothing has been recorded."
                )
                return

            # Mise à jour des infos VIP (note)
            info = update_vip_info(vip_user_id, note=note_text)

            topic_id = info.get("topic_id")
            panel_message_id = info.get("panel_message_id")
            admin_name = (
                info.get("admin_name")
                or message.from_user.username
                or message.from_user.first_name
                or str(admin_id)
            )
            full_note = info.get("note", note_text)
            if topic_id and panel_message_id:
                panel_text = (
                    "🧐 VIP CONTROL PANEL\n\n"
                    f"👤 Client : {vip_user_id}\n"
                    f"📒 Notes : {full_note}\n"
                    f"👤 Admin in charge : {admin_name}"
                )

                kb = InlineKeyboardMarkup()
                kb.add(
                    InlineKeyboardButton("✅ Take charge", callback_data=f"prendre_{vip_user_id}"),
                    InlineKeyboardButton("📝 Add a note", callback_data=f"annoter_{vip_user_id}")
                )

                await bot.edit_message_text(
                    chat_id=STAFF_GROUP_ID,
                    message_id=panel_message_id,
                    text=panel_text,
                    reply_markup=kb
                )

                await bot.send_message(
                    chat_id=admin_id,
                    text="✅ Note recorded and panel updated."
                )
                return
            else:
                await bot.send_message(
                    chat_id=admin_id,
                    text="⚠️ VIP panel not found for this client."
                )
                return

        # 💬 CAS NORMAL (pas en mode note) → on garde ton comportement d'origine
        await bot.send_message(chat_id=admin_id, text="❗ Unable to identify recipient.")
        return

    # 3) lire /envXX
    texte = message.caption or message.text or ""
    match = re.search(r"/env(\d+|vip)", texte.lower())
    if not match:
        await bot.send_message(chat_id=admin_id, text="❗ No valid /envXX code detected.")
        return

    code = match.group(1)

    # ⚠️ on utilise le dict GLOBAL défini plus haut
    lien = liens_paiement.get(code)
    if not lien:
        await bot.send_message(chat_id=admin_id, text="❗ This amount is not recognized in the available links.")
        return

    # on remplace /envXX par le vrai lien Stripe
    nouvelle_legende = re.sub(r"/env(\d+|vip)", lien, texte, flags=re.IGNORECASE)

    # 4) si l'admin a joint un média → on le stocke en "contenu en attente"
    if message.photo or message.video or message.document:
        if message.photo:
            file_id = message.photo[-1].file_id
            content_type = types.ContentType.PHOTO
        elif message.video:
            file_id = message.video.file_id
            content_type = types.ContentType.VIDEO
        else:
            file_id = message.document.file_id
            content_type = types.ContentType.DOCUMENT

        contenus_en_attente[user_id] = {
            "file_id": file_id,
            "type": content_type,
            # on enlève le /envXX dans la caption envoyée après paiement
            "caption": re.sub(r"/env(\d+|vip)", "", texte, flags=re.IGNORECASE).strip()
        }
        from vip_topics import ensure_topic_for_vip
        dummy_user = types.User(id=user_id, is_bot=False, first_name=str(user_id))
        topic_id = await ensure_topic_for_vip(dummy_user)

        await bot.request(
            "sendMessage",
            {
                "chat_id": STAFF_GROUP_ID,
                "message_thread_id": topic_id,
                "text": f"✅ Content ready for the user {user_id}."
            }
        )

        # cas où le client avait déjà payé → on envoie direct
        if user_id in paiements_en_attente_par_user:
            contenu = contenus_en_attente[user_id]
            if contenu["type"] == types.ContentType.PHOTO:
                await bot.send_photo(chat_id=user_id, photo=contenu["file_id"], caption=contenu.get("caption"))
            elif contenu["type"] == types.ContentType.VIDEO:
                await bot.send_video(chat_id=user_id, video=contenu["file_id"], caption=contenu.get("caption"))
            elif contenu["type"] == types.ContentType.DOCUMENT:
                await bot.send_document(chat_id=user_id, document=contenu["file_id"], caption=contenu.get("caption"))

            paiements_en_attente_par_user.discard(user_id)
            contenus_en_attente.pop(user_id, None)
            return

    # 5) sinon → on envoie le flouté + lien
    await bot.send_photo(
        chat_id=user_id,
        photo=DEFAULT_FLOU_IMAGE_FILE_ID,
        caption=nouvelle_legende
    )
    await bot.send_message(
        chat_id=user_id,
        text=f"_🔒 This content {code} $ is locked. Click on the link above to unlock it._",
 
        parse_mode="Markdown"
    )



@dp.message_handler(lambda message: message.text == "📖 Control" and is_admin(message.from_user.id))
async def show_commandes_admin(message: types.Message):
    commandes = (
        "📖 *List of available commands :*\n\n"
        "🔒 */envxx* – Send paid content $\n"
        "_Enter this command with the correct amount (ex. /env29) to send blurred content with a payment link for $29. Your customer will receive a blurred image directly with the payment link._\n\n"
        "⚠️ ** – Don't forget to select the message from the customer you want to reply to\n\n"
        "⚠️ ** – Here is the price list : 9, 19, 29, 39, 49, 59, 69, 79, 89, 99, 109, 119, 129, 139, 149, 159, 169, 179, 189, 199, 209, 500, 1000\n\n"
        "📬 *Need help ?* Email me : novapulse.online@gmail.com"
    )

    # Création du bouton inline "Mise à jour"
    inline_keyboard = InlineKeyboardMarkup()
    inline_keyboard.add(InlineKeyboardButton("🛠️ Update", callback_data="maj_bot"))

    await message.reply(commandes, parse_mode="Markdown", reply_markup=inline_keyboard)


# Callback quand on clique sur le bouton inline
@dp.callback_query_handler(lambda call: call.data == "maj_bot")
async def handle_maj_bot(call: types.CallbackQuery):
    await bot.answer_callback_query(call.id)
    await bot.send_message(call.message.chat.id, "🔄 Click to start the update ➡️ : /start")

@dp.message_handler(lambda message: message.text == "📊 Statistics" and is_admin(message.from_user.id))
async def show_stats_direct(message: types.Message):
    await handle_stat(message)


# ======================== IMPORTS & VARIABLES ========================

# ========== HANDLER ADMIN : réponses privées + messages groupés ==========

@dp.message_handler(lambda message: is_admin(message.from_user.id), content_types=types.ContentType.ANY)
async def handle_admin_message(message: types.Message):
    admin_id = message.from_user.id
    mode = admin_modes.get(admin_id)

    print(
        f"[ADMIN_MSG] from admin_id={admin_id}, chat_id={message.chat.id}, "
        f"reply_to={getattr(message.reply_to_message, 'message_id', None)}"
    )

    # 1) MENU ENVOI GROUPÉ
    if message.text == "✉️ Message to all VIPs":
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("📩 Free message", callback_data="vip_message_gratuit")
        )
        await bot.send_message(
            chat_id=admin_id,
            text="🧩 Choose the type of message to send to all VIPs :",
            reply_markup=kb
        )
        return

    # 2) MODE DIFFUSION GROUPÉE
    if mode == "en_attente_message":
        admin_modes[admin_id] = None
        await traiter_message_groupé(message, admin_id=admin_id)
        return

    # 3) RÉPONSE À UN CLIENT (COMPORTEMENT NORMAL)

    # 🔐 On oblige : reply + dans le STAFF_GROUP
    if not message.reply_to_message or message.chat.id != STAFF_GROUP_ID:
        await bot.send_message(
            chat_id=admin_id,
            text="❗To reply to a customer, reply to the message forwarded by the customer in the staff group (in their topic).",
            parse_mode="Markdown"
        )
        return

    replied_msg_id = message.reply_to_message.message_id
    key = (message.chat.id, replied_msg_id)
    user_id = pending_replies.get(key)

    print(f"[ADMIN_MSG] lookup pending_replies key={key} -> user_id={user_id}")

    # 🔥 Sécurité : on refuse d'envoyer vers un admin
    if (
        not user_id
        or user_id == admin_id
        or user_id in authorized_admin_ids
        or user_id == OWNER_ID
    ):
        await bot.send_message(
            chat_id=admin_id,
            text="❗Unable to identify the recipient *client*. "
                 "Respond appropriately to the **last message forwarded from the customer** in their thread.",
            parse_mode="Markdown"
        )
        return

    # 4) Envoi vers le client
    try:
        if message.text:
            await bot.send_message(chat_id=user_id, text=message.text)

        elif message.photo:
            await bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=message.caption or ""
            )

        elif message.video:
            await bot.send_video(
                chat_id=user_id,
                video=message.video.file_id,
                caption=message.caption or ""
            )

        elif message.document:
            await bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=message.caption or ""
            )

        elif message.voice:
            await bot.send_voice(
                chat_id=user_id,
                voice=message.voice.file_id
            )

        elif message.audio:
            await bot.send_audio(
                chat_id=user_id,
                audio=message.audio.file_id,
                caption=message.caption or ""
            )

        else:
            await bot.send_message(
                chat_id=admin_id,
                text="📂 Message type not supported."
            )

    except Exception as e:
        await bot.send_message(
            chat_id=admin_id,
            text=f"❗Erreur admin -> client : {e}"
        )


# ========== IMPORTS ESSENTIELS ==========
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== HANDLER CLIENT : transfert vers admin ==========

from ban_storage import ban_list  # à ajouter tout en haut si pas déjà fait


STAFF_GROUP_ID = int(os.getenv("STAFF_GROUP_ID", "0"))

@dp.message_handler(
    lambda message: message.chat.type == "private" and not is_admin(message.from_user.id),
    content_types=types.ContentType.ANY
)
async def relay_from_client(message: types.Message):
    """
    Tous les clients (VIP ou non) sont transférés dans un topic dédié
    dans le STAFF_GROUP. Le statut VIP sert uniquement aux stats / envois groupés.
    """
    user_id = message.from_user.id

    print(f"[RELAY] message from {user_id} (chat {message.chat.id}), authorized={user_id in authorized_users}")

    # 1) Vérifier la ban_list
    for admin_id, clients_bannis in ban_list.items():
        if user_id in clients_bannis:
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await bot.send_message(
                    user_id,
                    "🚫 You have been banned, you can no longer send messages."
                )
            except Exception:
                pass
            return

    # 2) Création / récupération du topic dédié pour ce client
    try:
        from vip_topics import ensure_topic_for_vip

        topic_id = await ensure_topic_for_vip(message.from_user)

        res = await bot.request(
            "copyMessage",
            {
                "chat_id": STAFF_GROUP_ID,
                "from_chat_id": message.chat.id,
                "message_id": message.message_id,
                "message_thread_id": topic_id,
            }
        )

        sent_msg_id = res.get("message_id")
        if sent_msg_id:
            pending_replies[(STAFF_GROUP_ID, sent_msg_id)] = message.chat.id

        print(f"✅ Message client reçu de {message.chat.id} et transféré dans le topic {topic_id}")
    except Exception as e:
        print(f"❌ Erreur transfert message client vers topic : {e}")


# 1. code pour le bouton prendre en charge début

@dp.callback_query_handler(lambda c: c.data.startswith("prendre_"))
async def handle_prendre_en_charge(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    data = callback_query.data  # ex: "prendre_8440217096"

    try:
        vip_user_id = int(data.split("_", 1)[1])
    except Exception:
        await callback_query.answer("Invalid VIP ID.", show_alert=True)
        return

    # Déterminer le nom de l'admin
    admin_name = (
        callback_query.from_user.username
        or callback_query.from_user.first_name
        or str(admin_id)
    )

    print(f"[VIP] Admin {admin_id} prend en charge VIP {vip_user_id} ({admin_name})")

    # On met à jour les infos VIP (ADMIN UNIQUEMENT)
    info = update_vip_info(
        vip_user_id,
        admin_id=admin_id,
        admin_name=admin_name,
    )

    panel_message_id = info.get("panel_message_id")
    note_text = info.get("note", "Aucune note")

    if not panel_message_id:
        await callback_query.answer("Unable to find the panel for this VIP.", show_alert=True)
        return

    panel_text = (
        "🧐 VIP CONTROL PANEL\n\n"
        f"👤 Client : {vip_user_id}\n"
        f"📒 Notes : {note_text}\n"
        f"👤 Admin in charge : {admin_name}"
    )

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Take charge", callback_data=f"prendre_{vip_user_id}"),
        InlineKeyboardButton("📝 Add a note", callback_data=f"annoter_{vip_user_id}")
    )

    # On met à jour le panneau
    await bot.edit_message_text(
        chat_id=STAFF_GROUP_ID,
        message_id=panel_message_id,
        text=panel_text,
        reply_markup=kb
    )

    await callback_query.answer("✅ You are now in charge of this VIP.")



# 1. code pour le bouton prendre en charge fin

# 1. code pour le bouton annoter début



@dp.callback_query_handler(lambda c: c.data and c.data.startswith("annoter_"))
async def handle_annoter_vip(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id

    # Vérifier qu'on clique bien depuis le STAFF_GROUP
    if callback_query.message.chat.id != STAFF_GROUP_ID:
        await callback_query.answer("Action reserved for staff.", show_alert=True)
        return

    # Récupère l'user_id du VIP depuis la callback
    try:
        user_id = int(callback_query.data.split("_", 1)[1])
    except Exception:
        await callback_query.answer("Invalid data.", show_alert=True)
        return

    # Si l'admin est déjà en mode note, renvoyer une info et ne rien re-créer
    if admin_id in pending_notes:
        current_target = pending_notes.get(admin_id)
        # Si c'est pour le même client, on informe
        if current_target == user_id:
            await callback_query.answer("📝 You are already in annotation mode for this client. Send your note in the topic.", show_alert=False)
            return
        # Sinon, prévenir que l'admin est déjà en mode note pour un autre client
        await callback_query.answer("🔔 You are currently in annotation mode for another client. Please finish or cancel first.", show_alert=True)
        return

    # On récupère les infos déjà stockées (topic_id, panel_message_id, etc.)
    info = update_vip_info(user_id)  # sans note/admin => juste retour du dict
    topic_id = info.get("topic_id")

    if not topic_id:
        await callback_query.answer("Unable to find the VIP topic.", show_alert=True)
        return

    # On passe cet admin en "mode note" pour ce user_id
    pending_notes[admin_id] = user_id

    # Marquer l'admin comme "en train d'annoter" visuellement (ferme le loader)
    await callback_query.answer()

    # ⚠️ ICI : on utilise bot.request pour poster DANS LE TOPIC
    try:
        await bot.request(
            "sendMessage",
            {
                "chat_id": STAFF_GROUP_ID,
                "message_thread_id": topic_id,
                "text": (
                    f"📝 Send your note to the customer now {user_id} in this topic.\n"
                    "➡️ The next message you write here will be saved as a NOTE.\n\n"
                    "If you want to cancel: press `/annuler_note`."
                ),
            },
        )
    except Exception as e:
        # Nettoyage si envoi échoue (pour éviter rester bloqué en pending)
        pending_notes.pop(admin_id, None)
        print(f"[NOTES] Erreur envoi prompt annotation (callback annoter_) : {e}")
        await callback_query.answer("Unable to send annotation prompt.", show_alert=True)




# 1. code pour le bouton annoter fin


# ========== CHOIX DANS LE MENU INLINE ==========

@dp.callback_query_handler(lambda call: call.data == "vip_message_gratuit")
async def choix_type_message_vip(call: types.CallbackQuery):
    await call.answer()
    admin_id = call.from_user.id

    admin_modes[admin_id] = "en_attente_message"

    await bot.send_message(
        chat_id=admin_id,
        text="✍️ Send now the message (text/photo/video) to be broadcast to all your VIPs for FREE."
    )



# ========== TRAITEMENT MESSAGE GROUPÉ GRATUIT ==========

async def traiter_message_groupé(message: types.Message, admin_id=None):
    admin_id = admin_id or message.from_user.id

    if message.text:
        pending_mass_message[admin_id] = {"type": "text", "content": message.text}
        preview = message.text

    elif message.photo:
        pending_mass_message[admin_id] = {
            "type": "photo",
            "content": message.photo[-1].file_id,
            "caption": message.caption or ""
        }
        preview = f"[Photo] {message.caption or ''}"

    elif message.video:
        pending_mass_message[admin_id] = {
            "type": "video",
            "content": message.video.file_id,
            "caption": message.caption or ""
        }
        preview = f"[Vidéo] {message.caption or ''}"

    elif message.audio:
        pending_mass_message[admin_id] = {
            "type": "audio",
            "content": message.audio.file_id,
            "caption": message.caption or ""
        }
        preview = f"[Audio] {message.caption or ''}"

    elif message.voice:
        pending_mass_message[admin_id] = {
            "type": "voice",
            "content": message.voice.file_id
        }
        preview = "[Note vocale]"

    else:
        await message.reply("❌ Message not supported.")
        return

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Confirm sending", callback_data="confirmer_envoi_groupé"),
        InlineKeyboardButton("❌ Cancel sending", callback_data="annuler_envoi_groupé")
    )
    await message.reply(f"Preview :\n\n{preview}", reply_markup=kb)



# ========== CALLBACKS ENVOI / ANNULATION GROUPÉ ==========

@dp.callback_query_handler(lambda call: call.data == "confirmer_envoi_groupé")
async def confirmer_envoi_groupé(call: types.CallbackQuery):
    await call.answer()
    admin_id = call.from_user.id
    message_data = pending_mass_message.get(admin_id)

    if not message_data:
        await call.message.edit_text("❌ No messages waiting to be sent.")
        return

    # 1️⃣ Récupérer l'e-mail de cet admin
    email = ADMIN_EMAILS.get(admin_id)
    if not email:
        await bot.send_message(
            chat_id=admin_id,
            text="❌ Your admin email is not configured in the bot. Talk to Nova Pulse to update it."
        )
        pending_mass_message.pop(admin_id, None)
        return

    # 2️⃣ Récupérer les VIPs de CET admin via Airtable
    try:
        vip_ids = list(get_vip_ids_for_admin_email(email))  # 🔹 helper à ajouter à côté de /stat
    except Exception as e:
        print(f"[MASS_VIP] Erreur en récupérant les VIPs pour {email} : {e}")
        await bot.send_message(
            chat_id=admin_id,
            text="❌ Unable to retrieve your VIP list at this time."
        )
        pending_mass_message.pop(admin_id, None)
        return

    if not vip_ids:
        await bot.send_message(
            chat_id=admin_id,
            text="ℹ️ No VIPs found for you. Nothing to send."
        )
        pending_mass_message.pop(admin_id, None)
        return

    await bot.send_message(
        chat_id=admin_id,
        text=f"⏳ Send message to {len(vip_ids)} VIP(s)..."
    )

    envoyes = 0
    erreurs = 0

    # 3️⃣ Envoi 100 % GRATUIT à ces VIPs
    for vip_id in vip_ids:
        try:
            vip_id = int(vip_id)

            if message_data["type"] == "text":
                await bot.send_message(chat_id=vip_id, text=message_data["content"])

            elif message_data["type"] == "photo":
                await bot.send_photo(
                    chat_id=vip_id,
                    photo=message_data["content"],
                    caption=message_data.get("caption", "")
                )

            elif message_data["type"] == "video":
                await bot.send_video(
                    chat_id=vip_id,
                    video=message_data["content"],
                    caption=message_data.get("caption", "")
                )

            elif message_data["type"] == "audio":
                await bot.send_audio(
                    chat_id=vip_id,
                    audio=message_data["content"],
                    caption=message_data.get("caption", "")
                )

            elif message_data["type"] == "voice":
                await bot.send_voice(
                    chat_id=vip_id,
                    voice=message_data["content"]
                )

            envoyes += 1

        except Exception as e:
            print(f"❌ Erreur envoi à {vip_id} : {e}")
            erreurs += 1

    await bot.send_message(
        chat_id=admin_id,
        text=f"✅ Sent to {envoyes} VIP(s).\n⚠️ Failures : {erreurs}"
    )
    pending_mass_message.pop(admin_id, None)


@dp.callback_query_handler(lambda call: call.data == "annuler_envoi_groupé")
async def annuler_envoi_groupé(call: types.CallbackQuery):
    await call.answer("❌ Sending canceled.")
    admin_id = call.from_user.id
    pending_mass_message.pop(admin_id, None)
    await call.message.edit_text("❌ Sending canceled.")



#mettre le tableau de vips
@dp.callback_query_handler(lambda c: c.data == "voir_mes_vips")
async def voir_mes_vips(callback_query: types.CallbackQuery):
    telegram_id = callback_query.from_user.id
    email = ADMIN_EMAILS.get(telegram_id)

    if not email:
        await bot.send_message(telegram_id, "❌ Your admin email is not recognized.")
        return

    await callback_query.answer("Loading your VIPs...")

    headers = {
        "Authorization": f"Bearer {os.getenv('AIRTABLE_API_KEY')}"
    }

    url = "https://api.airtable.com/v0/appdA5tvdjXiktFzq/tblwdps52XKMk43xo"
    params = {
        "filterByFormula": f"{{Email}} = '{email}'"
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        await bot.send_message(telegram_id, f"❌ Airtable error : {response.status_code}\n\n{response.text}")
        return

    records = response.json().get("records", [])
    if not records:
        await bot.send_message(telegram_id, "📭 No records found for you.")
        return

    # Étape 1 : repérer les pseudos ayant AU MOINS un paiement > 0 (Type acces = paiement ou vip)
    pseudos_vip = set()
    for r in records:
        f = r.get("fields", {})
        pseudo = (f.get("Pseudo Telegram", "") or "").strip()
        type_acces = (f.get("Type acces", "") or "").strip().lower()
        montant_raw = f.get("Montant")

        try:
            montant = float(montant_raw or 0)
        except Exception:
            montant = 0.0

        if pseudo and montant > 0 and type_acces in ("paiement", "vip"):
            pseudos_vip.add(pseudo)

    if not pseudos_vip:
        await bot.send_message(telegram_id, "📭 You don't have any VIP customers yet (no payments recorded).")
        return

    # Étape 2 : additionner TOUS les montants (Paiement + VIP) de ces pseudos uniquement
    montants_par_pseudo = {}
    for r in records:
        f = r.get("fields", {})
        pseudo = (f.get("Pseudo Telegram", "") or "").strip()
        montant_raw = f.get("Montant")

        if not pseudo or pseudo not in pseudos_vip:
            continue

        try:
            montant_float = float(montant_raw or 0)
        except Exception:
            montant_float = 0.0

        if pseudo not in montants_par_pseudo:
            montants_par_pseudo[pseudo] = 0.0

        montants_par_pseudo[pseudo] += montant_float

    try:
        # Construction du message final avec tri et top 3
        message = "📋 Here are your VIP customers (with all their payments) :\n\n"
        sorted_vips = sorted(montants_par_pseudo.items(), key=lambda x: x[1], reverse=True)

        for pseudo, total in sorted_vips:
            message += f"👤 @{pseudo} — {round(total)} $\n"

        # 🏆 Top 3
        top3 = sorted_vips[:3]
        if top3:
            message += "\n🏆 *Top 3 clients :*\n"
            for i, (pseudo, total) in enumerate(top3):
                place = ["🥇", "🥈", "🥉"]
                emoji = place[i] if i < len(place) else f"#{i+1}"
                message += f"{emoji} @{pseudo} — {round(total)} $\n"

        await bot.send_message(telegram_id, message, parse_mode="Markdown")

    except Exception as e:
        import traceback
        error_text = traceback.format_exc()
        print("❌ ERREUR DANS VIPS + TOP 3 :\n", error_text)
        await bot.send_message(telegram_id, "❌ An error occurred while displaying VIPs.")

#fin du 19 juillet 2025 mettre le tableau de vips
