"""Equivalencias de nombres de clientes.
Clave: como aparece en alguna planilla. Valor: el nombre unico que usa el dashboard.
Para sumar un caso nuevo, agregar una linea al diccionario."""
import unicodedata

ALIAS = {
    "Casa Cigal - Flor Peluffo": "Casa Cigal",
    "Delician - Con Sabor S.A.": "Delician",
    "Delician - Mariana Cian": "Delician",
    "Rocio Macarena Muñoz": "Rocio Muñoz",
    "Almirante Donn": "Almirante Dönn",
    "Juan Neme": "Cerveza Gringa (Juan Neme)",
}


def _clave(nombre):
    """Sin acentos, mayusculas y espacios simples: 'Rocío  Muñoz' -> 'ROCIO MUNOZ'."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", str(nombre))
                          if unicodedata.category(c) != "Mn")
    return " ".join(sin_acentos.split()).upper()


_ALIAS = {_clave(k): v for k, v in ALIAS.items()}


def cliente_canonico(nombre):
    n = " ".join(str(nombre).split())
    return _ALIAS.get(_clave(n), n)
