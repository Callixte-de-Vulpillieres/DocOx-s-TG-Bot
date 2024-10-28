from abc import ABC, abstractmethod
from billard import database
import numpy as np
from scipy.optimize import minimize
import matplotlib.pyplot as plt


class Model(ABC):
    def __init__(self):
        self.parties = database.execute("SELECT * FROM game").fetchall()
        self.joueurs = {
            joueur[0]: None
            for joueur in database.execute("SELECT * FROM user").fetchall()
        }

    @abstractmethod
    def partie(self, partie):
        """Méthode abstraite pour traiter une partie
        Renvoie l'écart prévision - réalité au carré et mets à jour l'elo des joueurs"""
        pass

    def get_bound(self, param):
        return (None, None)

    def evaluer(self):
        res = 0.0
        for partie in self.parties:
            res += self.partie(partie)
        return res / len(self.parties)

    @abstractmethod
    def reinitialiser(self):
        pass

    @abstractmethod
    def get_parametres(self):
        pass

    def optimiser(self):
        params_noms = self.get_parametres()
        params__valeurs = [getattr(self, param) for param in params_noms]

        def fonction_objectif(x):
            self.reinitialiser()
            for i, param in enumerate(params_noms):
                setattr(self, param, x[i])
            return self.evaluer()

        return minimize(
            fonction_objectif,
            params__valeurs,
            bounds=[self.get_bound(param) for param in params_noms],
            method="Nelder-Mead",
        )


class ModelElo(Model):
    def __init__(self):
        super().__init__()
        self.k1 = 0
        self.k2 = 0
        self.k3 = 1 / 2
        self.facteur = 400.0
        self.joueurs = {joueur: (700.0, 0) for joueur in self.joueurs.keys()}

    def partie(self, partie):
        vainqueurs = set()
        defaits = set()
        for i, identifient in enumerate(partie[2:8]):
            if identifient is not None:
                if (i + 1) % 2 == partie[8]:
                    vainqueurs.add(identifient)
                else:
                    defaits.add(identifient)
        moyenne_vainqueurs = sum([self.joueurs[i][0] for i in vainqueurs]) / len(
            vainqueurs
        )
        moyenne_defaits = sum([self.joueurs[i][0] for i in defaits]) / len(defaits)
        probabilite = 1 / (
            1 + 10 ** ((moyenne_defaits - moyenne_vainqueurs) / self.facteur)
        )
        for i in vainqueurs:
            K = self.k1 + self.k2 * (1 + self.joueurs[i][1]) ** (-self.k3)
            self.joueurs[i] = (
                self.joueurs[i][0] + K * (1 - probabilite) / len(vainqueurs),
                self.joueurs[i][1] + 1,
            )
        for i in defaits:
            K = self.k1 + self.k2 * (1 + self.joueurs[i][1]) ** (-self.k3)
            self.joueurs[i] = (
                self.joueurs[i][0] + K * (probabilite - 1) / len(defaits),
                self.joueurs[i][1] + 1,
            )
        return (1 - probabilite) ** 2

    def reinitialiser(self):
        self.joueurs = {joueur: (700.0, 0) for joueur in self.joueurs.keys()}

    def get_parametres(self):
        return ["k1", "k2"]

    def get_bound(self, param):
        return (0, None)

    def leaderboard(self):
        jrs = sorted(self.joueurs.items(), key=lambda x: x[1][0], reverse=True)
        for joueur, valeurs in jrs:
            pseudo = database.execute(
                "SELECT name FROM user WHERE id = ?", (joueur,)
            ).fetchone()[0]
            print(pseudo, valeurs[0])

    def surface(self, k1min, k1max, k2min, k2max):
        k1 = np.linspace(k1min, k1max, 100)
        k2 = np.linspace(k2min, k2max, 100)
        k1, k2 = np.meshgrid(k1, k2)
        z = np.zeros(k1.shape)
        for i in range(k1.shape[0]):
            for j in range(k1.shape[1]):
                self.reinitialiser()
                self.k1 = k1[i, j]
                self.k2 = k2[i, j]
                z[i, j] = self.evaluer()
        return k1, k2, z


model = ModelElo()
print(model.evaluer())

model.leaderboard()

res = model.optimiser()
print(res)
model.reinitialiser()
model.k1 = res.x[0]
model.k2 = res.x[1]
# model.k3 = res.x[2]
print(model.evaluer())
model.leaderboard()
print(f"k1 = {model.k1}, k2 = {model.k2}, k3 = {model.k3}")

k1, k2, z = model.surface(0, 5 + model.k1 * 2, 0, 5 + model.k2 * 2)

fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
surf = ax.plot_surface(k1, k2, z, cmap="viridis", vmin=np.min(z), vmax=np.max(z))
ax.set_xlabel("k1")
ax.set_ylabel("k2")
ax.set_zlabel("MSE")
fig.colorbar(surf, ax=ax, orientation="horizontal")
plt.show()
