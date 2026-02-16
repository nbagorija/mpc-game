# crypto_utils.py

import random
from config import PRIME, FIELD_SIZE


def mod(x, p=PRIME):
    """Остаток по модулю, всегда неотрицательный."""
    return x % p


def generate_additive_shares(secret, num_parties, p=PRIME):
    """
    Аддитивный secret sharing: разбивает secret на num_parties долей,
    сумма которых по модулю p равна secret.
    """
    shares = [random.randint(0, p - 1) for _ in range(num_parties - 1)]
    last_share = mod(secret - sum(shares), p)
    shares.append(last_share)
    return shares


def reconstruct_additive(shares, p=PRIME):
    """Восстанавливает секрет из аддитивных долей."""
    return mod(sum(shares), p)


def random_nonzero(p=PRIME):
    """Случайное ненулевое число по модулю p."""
    while True:
        r = random.randint(1, p - 1)
        if r != 0:
            return r