import logging
from datetime import datetime
import sqlite3
from telegram import Update, User, InlineKeyboardButton, InlineKeyboardMarkup

database_con = sqlite3.connect("billard.db")
database = database_con.cursor()

partie_en_cours = None


class Joueur:
    def __init__(self, user: User):
        self.id = user.id
        self.pseudo = user.username if user.username else user.first_name

        query = database.execute("SELECT * FROM user WHERE id = ?", (self.id,))
        user_db = query.fetchone()
        if user_db is None:
            database.execute(
                "INSERT INTO user VALUES (?, ?, 700)", (self.id, self.pseudo)
            )
            database_con.commit()
            self.elo = 700.0
        else:
            self.elo = user_db[2]
            if self.pseudo != user_db[1]:
                database.execute(
                    "UPDATE user SET name = ? WHERE id = ?", (self.pseudo, self.id)
                )
                database_con.commit()

    def set_elo(self, elo_additionnel):
        nbre_parties = database.execute(
            "SELECT COUNT(*) FROM game WHERE joueur1_eq1 = ? OR joueur2_eq1 = ? OR joueur3_eq1 = ? OR joueur1_eq2 = ? OR joueur2_eq2 = ? OR joueur3_eq2 = ?",
            (self.id, self.id, self.id, self.id, self.id, self.id),
        ).fetchone()[0]
        K = 50 / (1 + nbre_parties / 20)
        self.elo += K * elo_additionnel
        database.execute("UPDATE user SET elo = ? WHERE id = ?", (self.elo, self.id))
        database_con.commit()
        return self.elo

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, o: object) -> bool:
        return self.id == o.id


class PartieEnCours:
    def __init__(self):
        self.team1 = set()
        self.team2 = set()
        self.message = None

    async def start(self, update: Update):
        logging.info("Début de la partie")
        boutons = [
            [InlineKeyboardButton("Rejoindre l'équipe 1", callback_data="1")],
            [InlineKeyboardButton("Rejoindre l'équipe 2", callback_data="2")],
            [InlineKeyboardButton("Annuler la partie", callback_data="Annuler")],
        ]
        self.message = await update.effective_chat.send_message(
            str(self), reply_markup=InlineKeyboardMarkup(boutons)
        )
        await self.message.pin()

    async def ajouter_joueur(self, joueur, team):
        if joueur in self.team1 or joueur in self.team2:
            return
        if team == 1:
            if len(self.team1) >= 3:
                return
            self.team1.add(joueur)
        else:
            if len(self.team2) >= 3:
                return
            self.team2.add(joueur)
        boutons = []
        if len(self.team1) < 3:
            boutons.append(
                [InlineKeyboardButton("Rejoindre l'équipe 1", callback_data="1")]
            )
        if len(self.team2) < 3:
            boutons.append(
                [InlineKeyboardButton("Rejoindre l'équipe 2", callback_data="2")]
            )
        boutons.append(
            [InlineKeyboardButton("Quitter mon équipe", callback_data="Quitter")]
        )
        if len(self.team1) > 0 and len(self.team2) > 0:
            boutons.append(
                [InlineKeyboardButton("Victoire équipe 1", callback_data="Victoire 1")]
            )
            boutons.append(
                [InlineKeyboardButton("Victoire équipe 2", callback_data="Victoire 2")]
            )
        boutons.append(
            [InlineKeyboardButton("Annuler la partie", callback_data="Annuler")]
        )
        await self.message.edit_text(
            str(self), reply_markup=InlineKeyboardMarkup(boutons)
        )

    async def retirer_joueur(self, joueur):
        if joueur in self.team1:
            self.team1.remove(joueur)
        elif joueur in self.team2:
            self.team2.remove(joueur)
        else:
            return
        boutons = []
        if len(self.team1) < 3:
            boutons.append(
                [InlineKeyboardButton("Rejoindre l'équipe 1", callback_data="1")]
            )
        if len(self.team2) < 3:
            boutons.append(
                [InlineKeyboardButton("Rejoindre l'équipe 2", callback_data="2")]
            )
        if len(self.team1) > 0 or len(self.team2) > 0:
            boutons.append(
                [InlineKeyboardButton("Quitter mon équipe", callback_data="Quitter")]
            )
        if len(self.team1) > 0 and len(self.team2) > 0:
            boutons.append(
                [InlineKeyboardButton("Victoire équipe 1", callback_data="Victoire 1")]
            )
            boutons.append(
                [InlineKeyboardButton("Victoire équipe 2", callback_data="Victoire 2")]
            )
        boutons.append(
            [InlineKeyboardButton("Annuler la partie", callback_data="Annuler")]
        )
        await self.message.edit_text(
            str(self), reply_markup=InlineKeyboardMarkup(boutons)
        )

    async def victoire(self, team):
        facteur = 400
        if team == 1:
            gagnants = self.team1
            perdants = self.team2
        else:
            gagnants = self.team2
            perdants = self.team1
        moyenne_gagnants = sum([joueur.elo for joueur in gagnants]) / len(gagnants)
        moyenne_perdants = sum([joueur.elo for joueur in perdants]) / len(perdants)
        elo_additionnel = 1 - 1 / (
            1 + 10 ** ((moyenne_perdants - moyenne_gagnants) / facteur)
        )
        await self.message.edit_text(str(self) + f"\n\nVictoire de l'équipe {team}")
        for joueur in gagnants:
            joueur.set_elo(elo_additionnel / len(gagnants))
        for joueur in perdants:
            joueur.set_elo(-elo_additionnel / len(perdants))
        await self.message.unpin()
        await self.message.chat.send_message(
            f"Victoire de l'équipe {team}\n\nÉquipe 1 :\n"
            + "\n".join(
                [f"{joueur.pseudo} ({round(joueur.elo,2)})" for joueur in self.team1]
            )
            + "\n\nÉquipe 2 :\n"
            + "\n".join(
                [f"{joueur.pseudo} ({round(joueur.elo,2)})" for joueur in self.team2]
            )
        )
        database.execute(
            "INSERT INTO game VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.message.message_id,
                datetime.now(),
                self.team1.pop().id,
                self.team2.pop().id,
                self.team1.pop().id if self.team1 else None,
                self.team2.pop().id if self.team2 else None,
                self.team1.pop().id if self.team1 else None,
                self.team2.pop().id if self.team2 else None,
                team == 1,
            ),
        )
        database_con.commit()

    def __str__(self):
        return (
            "Équipe 1 :\n"
            + "\n".join(
                [f"{joueur.pseudo} ({round(joueur.elo,2)})" for joueur in self.team1]
            )
            + "\n\nÉquipe 2 :\n"
            + "\n".join(
                [f"{joueur.pseudo} ({round(joueur.elo,2)})" for joueur in self.team2]
            )
        )


async def start(update: Update, context):
    global partie_en_cours
    if partie_en_cours is not None:
        await update.message.reply_text("Une partie est déjà en cours")
        return
    partie_en_cours = PartieEnCours()
    await partie_en_cours.start(update)


async def leaderboard(update: Update, context):
    joueurs = database.execute(
        "SELECT id FROM user ORDER BY elo DESC LIMIT 10"
    ).fetchall()
    rep = "**Leaderboard**\n\n"
    for i, joueur in enumerate(joueurs):
        id = await update.effective_chat.get_member(joueur[0])
        vrai_joueur = Joueur(id.user)
        rep += f"**{i+1}** — {vrai_joueur.pseudo} — **{round(vrai_joueur.elo,2)}**\n"
    await update.message.reply_text(rep)


async def callback(update: Update, context):
    logging.info("Callback : %s", update.callback_query.data)
    global partie_en_cours
    if partie_en_cours is None:
        await update.callback_query.answer("Aucune partie en cours")
        return
    if update.callback_query.data == "1":
        await partie_en_cours.ajouter_joueur(Joueur(update.callback_query.from_user), 1)
    elif update.callback_query.data == "2":
        await partie_en_cours.ajouter_joueur(Joueur(update.callback_query.from_user), 2)
    elif update.callback_query.data == "Quitter":
        await partie_en_cours.retirer_joueur(Joueur(update.callback_query.from_user))
    elif update.callback_query.data == "Victoire 1":
        await partie_en_cours.victoire(1)
        partie_en_cours = None
    elif update.callback_query.data == "Victoire 2":
        await partie_en_cours.victoire(2)
        partie_en_cours = None
    elif update.callback_query.data == "Annuler":
        await partie_en_cours.message.unpin()
        await partie_en_cours.message.delete()
        partie_en_cours = None
    await update.callback_query.answer()
