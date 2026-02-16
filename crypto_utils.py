# crypto_utils.py

import random


def generate_additive_shares(secret, num_parties, p=None):
    """
    Аддитивный secret sharing: разбивает secret на num_parties долей,
    сумма которых по модулю p равна secret.
    """
    if p is None:
        from config import PRIME
        p = PRIME
    shares = [random.randint(0, p - 1) for _ in range(num_parties - 1)]
    last_share = (secret - sum(shares)) % p
    shares.append(last_share)
    return shares


def reconstruct_additive(shares, p=None):
    """Восстанавливает секрет из аддитивных долей."""
    if p is None:
        from config import PRIME
        p = PRIME
    return sum(shares) % p