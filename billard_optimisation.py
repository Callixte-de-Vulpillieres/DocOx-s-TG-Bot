from abc import ABC, abstractmethod
import numpy as np
from scipy.optimize import minimize
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.animation import FuncAnimation

from billard import database


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

    def evaluer(self, max_parties=None):
        res = 0.0
        parties = self.parties
        if max_parties is not None:
            parties = parties[:max_parties]
        for partie in parties:
            res += self.partie(partie)
        return 0 if max_parties == 0 else res / len(parties)

    @abstractmethod
    def reinitialiser(self):
        pass

    @abstractmethod
    def get_parametres(self):
        pass

    def optimiser(self, max_parties=None):
        params_noms = self.get_parametres()
        params_valeurs = [getattr(self, param) for param in params_noms]

        def fonction_objectif(x):
            self.reinitialiser()
            for i, param in enumerate(params_noms):
                setattr(self, param, x[i])
            return self.evaluer(max_parties=max_parties)

        return minimize(
            fonction_objectif,
            params_valeurs,
            bounds=[self.get_bound(param) for param in params_noms],
        )


class ModelElo(Model):
    def __init__(self):
        super().__init__()
        self.k1 = 20
        self.k2 = 30
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
        return ["k1", "k2", "k3"]

    def get_bound(self, param):
        if param == "k3":
            return (None, None)
        return (None, None)

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
model.k3 = res.x[2]
print(model.evaluer())
model.leaderboard()
print(f"k1 = {model.k1}, k2 = {model.k2}, k3 = {model.k3}")

fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
N = 100
k3max = 3

# Calculate Z values
k3s = np.linspace(0, k3max, N + 1)
Z = []
k1, k2 = None, None
for k3 in k3s:
    print(f"Calculating for k3 = {k3}")
    model.k3 = k3
    k1, k2, z = model.surface(0, 150, 0, 150)
    Z.append(z)
vmin, vmax = np.min(Z), np.max(Z)

# Initialize plot
k3_slider = Slider(
    plt.axes([0.25, 0.01, 0.65, 0.03]), "k3", 0, k3max, valinit=0, valstep=k3max / N
)
surf = ax.plot_surface(k1, k2, Z[0], cmap="viridis", vmin=vmin, vmax=vmax)
ax.set_xlabel("k1")
ax.set_ylabel("k2")
ax.set_zlabel("MSE")
fig.colorbar(surf, ax=ax, orientation="horizontal")


# Update function for the slider
def update(val):
    index = int(round(k3_slider.val * N / k3max))
    global surf
    surf.remove()  # Remove the previous surface plot
    surf = ax.plot_surface(k1, k2, Z[index], cmap="viridis", vmin=vmin, vmax=vmax)
    fig.canvas.draw_idle()


k3_slider.on_changed(update)


# Animate function
def animate(i):
    k3_slider.set_val(i * k3max / N)


ani = FuncAnimation(fig, animate, frames=N + 1, repeat=True)
ani.save("optimisation.gif", writer="imagemagick", fps=10)

plt.show()

# x = [i for i in range(len(model.parties))]
# k1s = []
# k2s = []
# k3s = []
# for i, partie in enumerate(model.parties):
#     print(f"Calculating for {i} parties")
#     model.reinitialiser()
#     model.k1 = 20
#     model.k2 = 30
#     model.k3 = 1 / 2
#     optim = model.optimiser(max_parties=i)
#     k1s.append(optim.x[0])
#     k2s.append(optim.x[1])
#     k3s.append(optim.x[2])

# # plotting on 2 graphs, one with two axes for k1 and k2, and one for k3
# fig, ax1 = plt.subplots()
# ax1.set_xlabel("Parties")
# ax1.set_ylabel("k1")
# ax1.plot(x[10:], k1s[10:], label="k1", color="tab:blue")
# ax1.plot(x[10:], k2s[10:], label="k2", color="tab:orange")
# ax1.legend(loc="upper left")
# ax2 = ax1.twinx()
# ax2.set_ylabel("k3")
# ax2.plot(x[10:], k3s[10:], label="k3", color="tab:green")
# ax2.legend(loc="upper right")
# plt.show()
