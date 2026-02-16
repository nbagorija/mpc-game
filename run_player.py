#!/usr/bin/env python3
# run_player.py

import argparse
from config import SERVER_HOST, SERVER_PORT, FIELD_SIZE
from player import Player


def main():
    parser = argparse.ArgumentParser(description="MPC Game: Угадай точку")
    parser.add_argument("nickname", help="Уникальный никнейм игрока")
    parser.add_argument("--host", default=SERVER_HOST, help=f"Адрес сервера (по умолчанию {SERVER_HOST})")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help=f"Порт (по умолчанию {SERVER_PORT})")
    parser.add_argument("--players", type=int, default=2, help="Количество игроков (по умолчанию 2)")
    parser.add_argument("--field", type=int, default=FIELD_SIZE, help=f"Размер поля (по умолчанию {FIELD_SIZE})")

    args = parser.parse_args()

    player = Player(
        nickname=args.nickname,
        host=args.host,
        port=args.port,
        field_size=args.field
    )

    try:
        player.play(args.players)
    except KeyboardInterrupt:
        print("\nИгра прервана")
        player.conn.close()


if __name__ == "__main__":
    main()