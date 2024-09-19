import logging
import random
import os
from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ApplicationBuilder, ContextTypes, ChatMemberHandler


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


async def ajout_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Utilisateur modifié")
    logging.info(update.chat_member.new_chat_member.status)
    logging.info(update.chat_member.new_chat_member.user.is_bot)
    logging.info(update.chat_member.old_chat_member.status)
    if (
        update.chat_member.new_chat_member.status == ChatMemberStatus.MEMBER
        and not update.chat_member.new_chat_member.user.is_bot
        and update.chat_member.old_chat_member.status
        in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED]
    ):
        logging.info("Ajout d'un admin")
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
        await update.chat_member.chat.set_administrator_custom_title(
            update.chat_member.new_chat_member.user.id, nom
        )


if __name__ == "__main__":
    application = ApplicationBuilder().token(os.getenv("TG_TOKEN")).build()

    handler = ChatMemberHandler(
        ajout_admin, chat_member_types=ChatMemberHandler.CHAT_MEMBER
    )
    application.add_handler(handler)

    application.run_polling(allowed_updates=["chat_member"])
