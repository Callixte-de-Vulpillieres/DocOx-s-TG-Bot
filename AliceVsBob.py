import logging
import random
import os
import unicodedata
from unidecode import unidecode
from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    ChatMemberHandler,
    MessageHandler,
    filters,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def strip_accents(s):
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def find_rust(text):
    text = strip_accents(text.lower()).translate(str.maketrans("", "", " \n\t\r"))
    r = [
        "r",
        "г",
        "ꭱ",
        "ꮢ",
        "ᖇ",
        "ᴦ",
        "ⲅ",
        "ꮁ",
        "𐓜",
        "ꝛ",
        "ꞧ",
        "ꭇ",
        "ꭉ",
        "🄬",
        "🅁",
        "🅡",
        "🆁",
        "🇷",
        "ʇ",
        "尺",
        "℟",
        "ℜ",
    ]
    u = [
        "u",
        "ս",
        "ʋ",
        "ᑌ",
        "𑣘",
        "ߎ",
        "ᶙ",
        "ꞹ",
        "ꭎ",
        "ꭏ",
        "ꭒ",
        "𐓶",
        "🅄",
        "🅤",
        "🆄",
        "🇺",
        "ц",
        "ᵾ",
        "s",
    ]
    s = ["s", "ѕ", "տ", "ꮥ", "ꮪ", "𐑈", "ꞩ", "ꟊ", "🅂", "🅢", "🆂", "🇸", "n", "丂"]
    t = ["ꭲ", "𑣜", "🝨", "τ", "t", "🇹", "🅃", "🅣", "🆃", "ҭ", "ꓤ", "ｲ"]
    for i in range(len(text) - 3):
        if text[i] in r or unidecode(text[i]) in r:
            if text[i + 1] in u or unidecode(text[i + 1]) in u:
                if text[i + 2] in s or unidecode(text[i + 2]) in s:
                    if text[i + 3] in t or unidecode(text[i + 3]) in t:
                        return True
    return False


async def ajout_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if (
        update.chat_member.new_chat_member.status == ChatMemberStatus.MEMBER
        and not update.chat_member.new_chat_member.user.is_bot
        and update.chat_member.old_chat_member.status
        in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED]
    ):
        logging.info(
            "Ajout d'un admin : %s", update.chat_member.new_chat_member.user.full_name
        )
        # Ajout de l'admin
        await update.chat_member.chat.promote_member(
            update.chat_member.new_chat_member.user.id,
            can_change_info=False,
            can_delete_messages=False,
            can_invite_users=True,
            can_restrict_members=False,
            can_pin_messages=True,
            can_promote_members=False,
            can_manage_chat=False,
            is_anonymous=True,
        )
        # Choix d'un nom aléatoire
        nom = random.choice(["Alice", "Bob"])
        logging.info("Nom d'admin : %s", nom)
        await update.chat_member.chat.set_administrator_custom_title(
            update.chat_member.new_chat_member.user.id, nom
        )


async def ban_on_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if find_rust(update.effective_message.text):
        logging.info("Message à supprimer : %s", update.effective_message.text)
        # Suppression du message
        await update.effective_message.delete()


if __name__ == "__main__":
    application = ApplicationBuilder().token(os.getenv("TG_TOKEN")).build()

    handler_member = ChatMemberHandler(
        ajout_admin, chat_member_types=ChatMemberHandler.CHAT_MEMBER
    )
    handler_message = MessageHandler(filters=filters.TEXT, callback=ban_on_word)

    application.add_handler(handler_member)
    application.add_handler(handler_message)

    application.run_polling(
        poll_interval=1, allowed_updates=["chat_member", "message", "edited_message"]
    )
