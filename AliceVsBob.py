import logging
import random
import os
import re
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
    # Create a regex to match "rust" and any variant with strange characters
    # like "rüst" or "rùst" or "Rսst"
    rust_regex = re.compile(r"(r|г)(u|ù|ü)st", re.IGNORECASE)
    # Check if the message contains the word "rust"
    if rust_regex.search(update.effective_message.text):
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
