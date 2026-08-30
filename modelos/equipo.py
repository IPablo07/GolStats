"""
modelos/equipo.py
──────────────────
Representa un equipo. Encapsula su lista de jugadores: el resto del
código no debe tocar equipo._jugadores directamente, sino usar los
métodos que expone la clase.
"""


class Equipo:
    def __init__(self, id, nombre, nombre_capitan, correo_capitan, logo_url=None):
        self.id = id
        self.nombre = nombre
        self.nombre_capitan = nombre_capitan
        self.correo_capitan = correo_capitan
        self.logo_url = logo_url
        self._jugadores = []          # lista privada (por convención, el guion bajo)
        self.activo = True

    def agregar_jugador(self, jugador):
        if jugador.numero_camiseta in [j.numero_camiseta for j in self._jugadores]:
            raise ValueError(
                f"El número {jugador.numero_camiseta} ya está ocupado en el equipo {self.nombre}"
            )
        self._jugadores.append(jugador)
        jugador.equipo = self
        return jugador

    def obtener_jugadores(self):
        return list(self._jugadores)   # devuelve una copia, no la lista real

    def cantidad_jugadores(self):
        return len(self._jugadores)

    def buscar_jugador_por_cedula(self, cedula):
        for jugador in self._jugadores:
            if jugador.cedula == cedula:
                return jugador
        return None

    def buscar_jugador_por_id(self, jugador_id):
        for jugador in self._jugadores:
            if jugador.id == jugador_id:
                return jugador
        return None

    def tiene_jugador(self, jugador):
        return jugador in self._jugadores

    def __repr__(self):
        return f"<Equipo {self.nombre} ({self.cantidad_jugadores()} jugadores)>"
