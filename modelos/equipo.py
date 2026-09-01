"""
modelos/equipo.py
──────────────────
Representa un equipo. Encapsula su lista de jugadores: el resto del
código no debe tocar equipo._jugadores directamente, sino usar los
métodos que expone la clase.
"""


class Equipo:
    """
    Un equipo inscrito en el torneo, con su plantilla de jugadores.

    El capitán no es una cuenta aparte: se guardan su nombre y su correo
    porque es a quien se le avisa del pago de la vocalía y a quien se le
    manda el recibo cuando termina el partido.
    """

    def __init__(self, id, nombre, nombre_capitan, correo_capitan, logo_url=None):
        self.id = id
        self.nombre = nombre
        self.nombre_capitan = nombre_capitan
        self.correo_capitan = correo_capitan
        self.logo_url = logo_url
        self._jugadores = []          # lista privada (por convención, el guion bajo)
        self.activo = True

    def agregar_jugador(self, jugador):
        """
        Suma un jugador a la plantilla y lo deja apuntando a este equipo.

        Lanza ValueError si el número de camiseta ya está ocupado: es la
        razón por la que _jugadores es privada y no se toca con append().
        """
        if jugador.numero_camiseta in [j.numero_camiseta for j in self._jugadores]:
            raise ValueError(
                f"El número {jugador.numero_camiseta} ya está ocupado en el equipo {self.nombre}"
            )
        self._jugadores.append(jugador)
        jugador.equipo = self
        return jugador

    def obtener_jugadores(self):
        """
        Devuelve una **copia** de la plantilla, no la lista interna.

        Así, si quien la recibe le hace append() o remove(), no está
        modificando el equipo por accidente.
        """
        return list(self._jugadores)
    
    def cambiar_numero(self, jugador, numero_nuevo):
        """
        Cambia el dorsal del jugador validando que no esté ocupado por otro.
        """
        if not self.tiene_jugador(jugador):
            raise ValueError(f"El jugador no pertenece al equipo {self.nombre}.")
        
        numero_nuevo = int(numero_nuevo)
        if numero_nuevo < 1 or numero_nuevo > 99:
            raise ValueError("El número de camiseta debe estar entre 1 y 99.")
            
        # Validar si el número está ocupado por OTRO jugador
        for j in self._jugadores:
            if j.numero_camiseta == numero_nuevo and j.id != jugador.id:
                raise ValueError(f"El número {numero_nuevo} ya está ocupado por otro jugador en el equipo.")
                
        jugador.numero_camiseta = numero_nuevo

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
