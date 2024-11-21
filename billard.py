import logging
import re
from math import sqrt
from datetime import datetime
import sqlite3
from telegram import Update, User, InlineKeyboardButton, InlineKeyboardMarkup

Billard = -1002425330756

database_con = sqlite3.connect("billard.db")
database = database_con.cursor()

partie_en_cours = None


class Joueur:
    def __init__(self, id):
        self.id = id
        self.pseudo = None
        self.nbre_parties = database.execute(
            "SELECT COUNT(*) FROM game WHERE joueur1_eq1 = ? OR joueur2_eq1 = ? OR joueur3_eq1 = ? OR joueur1_eq2 = ? OR joueur2_eq2 = ? OR joueur3_eq2 = ?",
            (self.id, self.id, self.id, self.id, self.id, self.id),
        ).fetchone()[0]

        query = database.execute("SELECT * FROM user WHERE id = ?", (self.id,))
        user_db = query.fetchone()
        if user_db is None:
            database.execute(
                "INSERT INTO user VALUES (?, ?, 700)", (self.id, self.pseudo)
            )
            self.elo = 700.0
        else:
            self.pseudo = user_db[1]
            self.elo = user_db[2]

    async def load(self, user: User):
        pseudo = user.username if user.username else user.first_name
        if pseudo != self.pseudo:
            self.pseudo = pseudo
            database.execute(
                "UPDATE user SET name = ? WHERE id = ?", (self.pseudo, self.id)
            )

    def set_elo(self, elo_additionnel, update=True):
        K = 5 * (4 + 6 / sqrt(1 + self.nbre_parties))
        self.elo += K * elo_additionnel
        if update:
            database.execute(
                "UPDATE user SET elo = ? WHERE id = ?", (self.elo, self.id)
            )
        self.nbre_parties += 1
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
        if team == 1:
            if joueur in self.team1 or len(self.team1) >= 3:
                return
            if joueur in self.team2:
                self.team2.remove(joueur)
            self.team1.add(joueur)
        else:
            if joueur in self.team2 or len(self.team2) >= 3:
                return
            if joueur in self.team1:
                self.team1.remove(joueur)
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
        facteur = 400.0
        if team == 1:
            gagnants = self.team1
            perdants = self.team2
        else:
            gagnants = self.team2
            perdants = self.team1
        moyenne_gagnants = sum([joueur.elo for joueur in gagnants]) / len(gagnants)
        moyenne_perdants = sum([joueur.elo for joueur in perdants]) / len(perdants)
        probabilite = 1 / (1 + 10 ** ((moyenne_perdants - moyenne_gagnants) / facteur))
        message = f"Partie terminée, victoire de l'équipe {team}\n\nÉquipe 1 :\n"
        for joueur in self.team1:
            message += f"{joueur.pseudo} ({round(joueur.elo,2)}"
            if team == 1:
                joueur.set_elo((1 - probabilite) / len(self.team1))
            else:
                joueur.set_elo((probabilite - 1) / len(self.team1))
            message += f" → {round(joueur.elo,2)})\n"
        message += "\nÉquipe 2 :\n"
        for joueur in self.team2:
            message += f"{joueur.pseudo} ({round(joueur.elo,2)}"
            if team == 2:
                joueur.set_elo((1 - probabilite) / len(self.team2))
            else:
                joueur.set_elo((probabilite - 1) / len(self.team2))
            message += f" → {round(joueur.elo,2)})\n"
        await self.message.edit_text(message)
        await self.message.unpin()
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
    nbre_j = re.search(r"\d+", update.effective_message.text)
    if nbre_j:
        nbre_j = int(nbre_j.group())
    else:
        nbre_j = 10
    joueurs = database.execute(
        "SELECT id FROM user ORDER BY elo DESC LIMIT ?", (nbre_j,)
    ).fetchall()
    rep = "<b>Classement :</b>\n\n"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, joueur in enumerate(joueurs):
        vrai_joueur = Joueur(joueur[0])
        # await vrai_joueur.load((await update.effective_chat.get_member(joueur[0])).user)
        database_con.commit()
        if i < 10:
            rep += (
                f"{emojis[i]} {vrai_joueur.pseudo} — <i>{round(vrai_joueur.elo)}</i>\n"
            )
        else:
            rep += f"{i+1}. {vrai_joueur.pseudo} — <i>{round(vrai_joueur.elo)}</i>\n"
    logging.info(rep)
    await update.message.reply_text(rep, parse_mode="HTML")


async def supprimer(update: Update, context):
    # Supprimer la dernière partie
    database.execute("SELECT * FROM game ORDER BY temps DESC LIMIT 1")
    last_game = database.fetchone()
    if last_game is None:
        await update.message.reply_text("Aucune partie à supprimer")
        return
    message = update.effective_message.reply_to_message
    if message is None:
        await update.message.reply_text("Répondre à la partie à supprimer")
        return
    if message.message_id != last_game[0]:
        await update.message.reply_text("On ne peut supprimer que la dernière partie")
        return

    database.execute("DELETE FROM game WHERE id = ?", (last_game[0],))
    # Mettre à jour les ELO
    texte: str = message.text
    # Pour chaque joueur, on récupère son ELO avant la partie
    for i in range(2, 8):
        if last_game[i] is not None:
            database.execute("SELECT name FROM user WHERE id = ?", (last_game[i],))
            pseudo = database.fetchone()[0]
            if pseudo is None:
                logging.error("Pseudo non trouvé pour %s", last_game[i])
                database_con.rollback()
                return
            indice = texte.index(pseudo)
            if indice == -1:
                logging.error("Pseudo non trouvé dans le texte")
                database_con.rollback()
                return
            ancien_elo = float(re.search(r"[-+]?(?:\d*\.*\d+)", texte[indice:]).group())
            database.execute(
                "UPDATE user SET elo = ? WHERE id = ?", (ancien_elo, last_game[i])
            )
    database_con.commit()
    await update.message.reply_text("Partie supprimée")
    logging.info("Partie supprimée")

async def stats(update: Update, context):
    # Statistiques sur un joueur
    joueur = Joueur(update.effective_user.id)
    await joueur.load(update.effective_user)
    parties = database.execute(
        "SELECT * FROM game WHERE joueur1_eq1 = ? OR joueur2_eq1 = ? OR joueur3_eq1 = ? OR joueur1_eq2 = ? OR joueur2_eq2 = ? OR joueur3_eq2 = ?",
        (joueur.id, joueur.id, joueur.id, joueur.id, joueur.id, joueur.id),
    ).fetchall()
    if len(parties) == 0:
        await update.message.reply_text("Aucune partie jouée")
        return
    victoires = 0
    defaites = 0
    stats_autres = {} # Stats quand avec ou contre d'autres joueurs. stats_autres[id] = [vict_ens, def_ens, vict_vs, def_vs]
    for partie in parties:
        vainqueurs = set()
        defaits = set()
        for i, identifient in enumerate(partie[2:8]):
            if identifient is not None:
                if (i + 1) % 2 == partie[8]:
                    vainqueurs.add(identifient)
                else:
                    defaits.add(identifient)
        if joueur.id in vainqueurs:
            victoires += 1
            for autre in vainqueurs:
                if autre != joueur.id:
                    if autre not in stats_autres:
                        stats_autres[autre] = [0, 0, 0, 0]
                    stats_autres[autre][0] += 1
            for autre in defaits:
                if autre not in stats_autres:
                    stats_autres[autre] = [0, 0, 0, 0]
                stats_autres[autre][2] += 1
        elif joueur.id in defaits:
            defaites += 1
            for autre in vainqueurs:
                if autre not in stats_autres:
                    stats_autres[autre] = [0, 0, 0, 0]
                stats_autres[autre][3] += 1
            for autre in defaits:
                if autre != joueur.id:
                    if autre not in stats_autres:
                        stats_autres[autre] = [0, 0, 0, 0]
                    stats_autres[autre][1] += 1
    
    # On va déterminer le meilleur pote, le meilleur allié, le pire allié et le pire ennemi
    def meilleur_pote_cmp(id):
        return stats_autres[id][0] + stats_autres[id][1]
    
    meilleur_pote = max(stats_autres, key=meilleur_pote_cmp)
    if meilleur_pote_cmp(meilleur_pote) == 0:
        meilleur_pote = None
    meilleur_pote_parties = meilleur_pote_cmp(meilleur_pote)
    
    def meilleur_allie_cmp(id):
        if stats_autres[id][0] + stats_autres[id][1] == 0:
            return 0
        return stats_autres[id][0]/(2+(stats_autres[id][0] + stats_autres[id][1]))

    meilleur_allie = max(stats_autres, key=meilleur_allie_cmp)
    if meilleur_allie_cmp(meilleur_allie) == 0:
        meilleur_allie = None
    meilleur_allie_parties = meilleur_pote_cmp(meilleur_allie)
    meilleur_allie_vict = stats_autres[meilleur_allie][0]
    

    def pire_allie_cmp(id):
        if stats_autres[id][0] + stats_autres[id][1] == 0:
            return 0
        return stats_autres[id][1]/(2+(stats_autres[id][0] + stats_autres[id][1]))
    
    pire_allie = max(stats_autres, key=pire_allie_cmp)
    if pire_allie_cmp(pire_allie) == 0:
        pire_allie = None
    pire_allie_parties = meilleur_pote_cmp(pire_allie)
    pire_allie_vict = stats_autres[pire_allie][0]
    

    def pire_ennemi_cmp(id):
        if stats_autres[id][2] + stats_autres[id][3] == 0:
            return 0
        return stats_autres[id][3]/(2+(stats_autres[id][2] + stats_autres[id][3]))
    
    pire_ennemi = max(stats_autres, key=pire_ennemi_cmp) 
    if pire_ennemi_cmp(pire_ennemi) == 0:
        pire_ennemi = None
    pire_ennemi_parties = stats_autres[pire_ennemi][2] + stats_autres[pire_ennemi][3]
    pire_ennemi_def = stats_autres[pire_ennemi][3]


    def meilleur_ennemi_cmp(id):
        if stats_autres[id][2] + stats_autres[id][3] == 0:
            return 0
        return stats_autres[id][2]/(2+(stats_autres[id][2] + stats_autres[id][3]))
    
    meilleur_ennemi = max(stats_autres, key=meilleur_ennemi_cmp)
    if meilleur_ennemi_cmp(meilleur_ennemi) == 0:
        meilleur_ennemi = None
    meilleur_ennemi_parties = stats_autres[meilleur_ennemi][2] + stats_autres[meilleur_ennemi][3]
    meilleur_ennemi_vict = stats_autres[meilleur_ennemi][2]

    # On retrouve les pseudo :
    if meilleur_pote is not None:
        database.execute("SELECT name FROM user WHERE id = ?", (meilleur_pote,))
        meilleur_pote = database.fetchone()[0]
    if meilleur_allie is not None:
        database.execute("SELECT name FROM user WHERE id = ?", (meilleur_allie,))
        meilleur_allie = database.fetchone()[0]
    if pire_allie is not None:
        database.execute("SELECT name FROM user WHERE id = ?", (pire_allie,))
        pire_allie = database.fetchone()[0]
    if pire_ennemi is not None:
        database.execute("SELECT name FROM user WHERE id = ?", (pire_ennemi,))
        pire_ennemi = database.fetchone()[0]
    if meilleur_ennemi is not None:
        database.execute("SELECT name FROM user WHERE id = ?", (meilleur_ennemi,))
        meilleur_ennemi = database.fetchone()[0]
    
    # On retrouve le classement du joueur
    classement = database.execute("SELECT COUNT(*) FROM user WHERE elo > ?", (joueur.elo,)).fetchone()[0] + 1

    rep = f"<b>Statistiques de {joueur.pseudo} :</b>\n\n"
    rep += f"Nombre de parties : {joueur.nbre_parties}\n"
    rep += f"Nombre de victoires : {victoires}\n"
    rep += f"Nombre de défaites : {defaites}\n"
    rep += f"ELO : {round(joueur.elo, 2)}\n"
    rep += f"Classement : {classement}\n\n"
    if meilleur_pote is not None:
        rep += f"Meilleur(e) pote : {meilleur_pote}, {meilleur_pote_parties} fois dans la même équipe !\n"
    if meilleur_allie is not None:
        rep += f"Meilleur(e) allié(e) : {meilleur_allie} ; {meilleur_allie_vict} victoire{'s' if meilleur_allie_vict != 1 else ''} sur {meilleur_allie_parties} partie{'' if meilleur_allie_parties == 1 else 's'} ensemble\n"
    if pire_allie is not None:
        rep += f"Pire allié(e) : {pire_allie} ; seulement {pire_allie_vict} victoire{'' if pire_allie_vict == 1 else 's'} sur {pire_allie_parties} partie{'' if pire_allie_parties == 1 else 's'} ensemble\n"
    if pire_ennemi is not None:
        rep += f"Pire ennemi(e) : {pire_ennemi} ; {pire_ennemi_def} défaite{'' if pire_ennemi_def == 1 else 's'} sur {pire_ennemi_parties} partie{'' if pire_ennemi_parties == 1 else 's'} contre lui ou elle\n"
    if meilleur_ennemi is not None:
        rep += f"Meilleur(e) ennemi(e) : {meilleur_ennemi} ;  {meilleur_ennemi_vict} victoire{'' if meilleur_ennemi_vict == 1 else 's'} sur {meilleur_ennemi_parties} partie{'' if meilleur_ennemi_parties == 1 else 's'} contre lui ou elle\n"

    await update.message.reply_text(rep, parse_mode="HTML")

async def recalcule_elo(update: Update, context):
    mse = 0
    # Check if the user is an admin
    if not update.effective_user.id in [
        admin.user.id for admin in await update.effective_chat.get_administrators()
    ]:
        await update.message.reply_text(
            "Seuls les administrateurs peuvent utiliser cette commande"
        )
        return
    parties = database.execute("SELECT * FROM game").fetchall()
    joueurs = {}
    logging.info("Recalcul des ELO")
    for j, partie in enumerate(parties):
        logging.info("Partie %s/%s", j, len(parties))
        vainqueurs = set()
        defaits = set()
        for i, identifient in enumerate(partie[2:8]):
            if identifient is not None:
                if identifient not in joueurs:
                    joueurs[identifient] = Joueur(identifient)
                    joueurs[identifient].nbre_parties = 0
                    joueurs[identifient].elo = 700.0
                if (i + 1) % 2 == partie[8]:
                    vainqueurs.add(identifient)
                else:
                    defaits.add(identifient)
        moyenne_vainqueurs = sum([joueurs[i].elo for i in vainqueurs]) / len(vainqueurs)
        moyenne_defaits = sum([joueurs[i].elo for i in defaits]) / len(defaits)
        probabilite = 1 / (1 + 10 ** ((moyenne_defaits - moyenne_vainqueurs) / 400))
        mse += (probabilite - 1) ** 2
        for i in vainqueurs:
            joueurs[i].set_elo((1 - probabilite) / len(vainqueurs), False)
        for i in defaits:
            joueurs[i].set_elo((probabilite - 1) / len(defaits), False)
    # database_con.rollback()
    database_con.commit()
    logging.info("Elo recalculés")
    logging.info("MSE : %s", mse / len(parties))
    for joueur in joueurs.values():
        joueur.set_elo(0)
        logging.info("%s : %s", joueur.pseudo, joueur.elo)
    await update.message.reply_text("Elo recalculés")


async def callback(update: Update, context):
    logging.info("Callback : %s", update.callback_query.data)
    global partie_en_cours
    if partie_en_cours is None:
        await update.callback_query.answer("Aucune partie en cours")
        return
    if update.callback_query.data == "1":
        appelant = Joueur(update.callback_query.from_user.id)
        await appelant.load(update.callback_query.from_user)
        await partie_en_cours.ajouter_joueur(appelant, 1)
        database_con.commit()
    elif update.callback_query.data == "2":
        appelant = Joueur(update.callback_query.from_user.id)
        await appelant.load(update.callback_query.from_user)
        await partie_en_cours.ajouter_joueur(appelant, 2)
        database_con.commit()
    elif update.callback_query.data == "Quitter":
        appelant = Joueur(update.callback_query.from_user.id)
        await partie_en_cours.retirer_joueur(appelant)
        database_con.commit()
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
