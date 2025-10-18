import logging

# import asyncio
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
    CommandHandler,
    CallbackQueryHandler,
    filters,
)
from billard import (
    start,
    leaderboard,
    wall_of_fame,
    callback,
    supprimer,
    recalcule_elo,
    stats,
    Billard,
)

AliceVsBob = -1002270674258
Test = -1002438805139


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def strip_accents(s):
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def find_rust(text):
    text = strip_accents(text.lower()).translate(str.maketrans("", "", " \n\t\r"))
    text = "".join(char for char in text if char.isprintable())
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
        "ℝ",
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
        "ᴜ",
        "⨿",
        "𝞄",
    ]
    st = ["ﬆ"]
    s = [
        "s",
        "ѕ",
        "տ",
        "ꮥ",
        "ꮪ",
        "𐑈",
        "ꞩ",
        "ꟊ",
        "🅂",
        "🅢",
        "🆂",
        "🇸",
        "n",
        "丂",
        "ƽ",
        "$",
    ]
    t = ["ꭲ", "𑣜", "🝨", "τ", "t", "🇹", "🅃", "🅣", "🆃", "ҭ", "ꓤ", "ｲ", "ƚ", "l", "𝓣"]
    for i in range(len(text) - 3):
        if (
            text[i] in r
            or text[i].lower() in r
            or unidecode(text[i]).lower() in r
            or unidecode(text[i]) in r
        ):
            if (
                text[i + 1] in u
                or unidecode(text[i + 1]).lower() in u
                or unidecode(text[i + 1]) in u
                or text[i + 1].lower() in u
            ):
                if (
                    text[i + 2] in s
                    or unidecode(text[i + 2]).lower() in s
                    or unidecode(text[i + 2]) in s
                    or text[i + 2].lower() in s
                ):
                    if (
                        text[i + 3] in t
                        or unidecode(text[i + 3]).lower() in t
                        or unidecode(text[i + 3]) in t
                        or text[i + 3].lower() in t
                    ):
                        return True
                elif (
                    text[i + 2] in st
                    or unidecode(text[i + 2]).lower() in st
                    or unidecode(text[i + 2]) in st
                    or text[i + 2].lower() in st
                ):
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

    # # Pour l'initialisation des commandes seulement
    # asyncio.run(
    #     application.bot.set_my_commands(
    #         [
    #             BotCommand("start", "Démarrer une partie"),
    #             BotCommand("leaderboard", "Afficher le classement"),
    #             BotCommand("supprimer", "Supprimer la dernière partie"),
    #         ],
    #         BotCommandScopeChat(Billard),
    #     )
    # )
    handler_member = ChatMemberHandler(
        ajout_admin, chat_member_types=ChatMemberHandler.CHAT_MEMBER, chat_id=AliceVsBob
    )
    handler_message = MessageHandler(
        filters=filters.TEXT & filters.Chat(AliceVsBob),
        callback=ban_on_word,
    )

    handler_start = CommandHandler(
        command="start", callback=start, filters=filters.Chat(Billard)
    )

    handler_leaderboard = CommandHandler(
        command="leaderboard",
        callback=leaderboard,
        filters=filters.Chat({Billard, Test}),
    )

    handler_wall_of_fame = CommandHandler(
        command="wall_of_fame",
        callback=wall_of_fame,
        filters=filters.Chat({Billard, Test}),
    )

    handler_supp = CommandHandler(
        command="supprimer", callback=supprimer, filters=filters.Chat(Billard)
    )

    handler_rec = CommandHandler(
        command="recalcule_elo",
        callback=recalcule_elo,
        filters=filters.Chat({Test, Billard}),
    )

    handler_stats = CommandHandler(
        command="stats",
        callback=stats,
        filters=filters.Chat(Billard) | filters.ChatType.PRIVATE,
    )

    handler_boutons = CallbackQueryHandler(callback=callback)
    application.add_handler(handler_member)
    application.add_handler(handler_message)
    application.add_handler(handler_start)
    application.add_handler(handler_leaderboard)
    application.add_handler(handler_supp)
    application.add_handler(handler_boutons)
    application.add_handler(handler_rec)
    application.add_handler(handler_stats)

    application.run_polling(
        poll_interval=1,
        allowed_updates=[
            Update.MESSAGE,
            Update.EDITED_MESSAGE,
            Update.CHAT_MEMBER,
            Update.CALLBACK_QUERY,
        ],
    )
