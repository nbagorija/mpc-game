# player.py

import json
import random
import time
from config import FIELD_SIZE, PRIME
from crypto_utils import generate_additive_shares, mod, random_nonzero
from network import RepeaterConnection


class Player:
    def __init__(self, nickname, host, port, field_size=FIELD_SIZE):
        self.nickname = nickname
        self.field_size = field_size
        self.conn = RepeaterConnection(host, port, nickname)
        self.peers = []
        self.all_players = []
        self.my_index = -1
        self.num_parties = 0
        self.shares_x = {}
        self.shares_y = {}
        self.my_total_share_x = 0
        self.my_total_share_y = 0

    def connect_and_wait(self, expected_players):
        self.conn.connect()
        print(f"\n[{self.nickname}] Ожидаю {expected_players - 1} других игроков...")
        while True:
            self.peers = self.conn.get_peers()
            current = len(self.peers) + 1
            print(f"[{self.nickname}] Подключено: {current}/{expected_players}")
            if current >= expected_players:
                break
            time.sleep(3)

        self.all_players = sorted(self.peers + [self.nickname])
        self.my_index = self.all_players.index(self.nickname)
        self.num_parties = len(self.all_players)
        print(f"[{self.nickname}] Все игроки: {self.all_players}")
        print(f"[{self.nickname}] Мой индекс: {self.my_index}")

    def wait_for_message(self, msg_type, extra_check=None, timeout=120):
        """Универсальный метод ожидания конкретного типа сообщения."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = deadline - time.time()
            raw = self.conn.recv_message(timeout=remaining)
            if not raw:
                continue
            try:
                data = json.loads(raw)
                if data.get("type") == msg_type:
                    if extra_check is None or extra_check(data):
                        return data
                # Не тот тип — вернуть в очередь
                self.conn.message_queue.append(raw)
            except json.JSONDecodeError:
                pass
        return None

    def sync_barrier(self, barrier_name):
        """Синхронизация: все отправляют ready и ждут от всех."""
        msg = json.dumps({
            "type": "barrier",
            "name": barrier_name,
            "from": self.nickname
        })
        self.conn.send_to(self.peers, msg)

        received = set()
        while len(received) < len(self.peers):
            data = self.wait_for_message(
                "barrier",
                extra_check=lambda d: d.get("name") == barrier_name
            )
            if data:
                received.add(data["from"])
        print(f"[{self.nickname}] Синхронизация '{barrier_name}' завершена")

    def generate_secret_point(self):
        my_x = random.randint(0, PRIME - 1)
        my_y = random.randint(0, PRIME - 1)

        shares_x = generate_additive_shares(my_x, self.num_parties)
        shares_y = generate_additive_shares(my_y, self.num_parties)

        for i, player in enumerate(self.all_players):
            if player == self.nickname:
                self.shares_x[self.nickname] = shares_x[i]
                self.shares_y[self.nickname] = shares_y[i]
            else:
                msg = json.dumps({
                    "type": "share",
                    "from": self.nickname,
                    "share_x": shares_x[i],
                    "share_y": shares_y[i]
                })
                self.conn.send_to(player, msg)

        received = 0
        while received < self.num_parties - 1:
            data = self.wait_for_message("share")
            if data:
                sender = data["from"]
                self.shares_x[sender] = data["share_x"]
                self.shares_y[sender] = data["share_y"]
                received += 1
                print(f"[{self.nickname}] Получена доля от {sender}")

        self.my_total_share_x = mod(sum(self.shares_x.values()))
        self.my_total_share_y = mod(sum(self.shares_y.values()))
        print(f"[{self.nickname}] Секретная точка Q сгенерирована")

    def check_guess(self, guesser, guess_x=None, guess_y=None):
        is_me = (guesser == self.nickname)

        if is_me:
            print(f"\n[{self.nickname}] Я угадываю: ({guess_x}, {guess_y})")
            shares_gx = generate_additive_shares(guess_x, self.num_parties)
            shares_gy = generate_additive_shares(guess_y, self.num_parties)

            my_share_gx = shares_gx[self.my_index]
            my_share_gy = shares_gy[self.my_index]

            for i, player in enumerate(self.all_players):
                if player != self.nickname:
                    msg = json.dumps({
                        "type": "guess_share",
                        "from": self.nickname,
                        "guesser": guesser,
                        "share_gx": shares_gx[i],
                        "share_gy": shares_gy[i]
                    })
                    self.conn.send_to(player, msg)
        else:
            data = self.wait_for_message(
                "guess_share",
                extra_check=lambda d: d.get("guesser") == guesser
            )
            my_share_gx = data["share_gx"]
            my_share_gy = data["share_gy"]

        time.sleep(0.5)

        d_x_share = mod(self.my_total_share_x - my_share_gx)
        d_y_share = mod(self.my_total_share_y - my_share_gy)

        msg = json.dumps({
            "type": "diff_share",
            "from": self.nickname,
            "d_x": d_x_share,
            "d_y": d_y_share,
            "guesser": guesser
        })
        self.conn.send_to(self.peers, msg)

        all_dx = {self.nickname: d_x_share}
        all_dy = {self.nickname: d_y_share}

        while len(all_dx) < self.num_parties:
            data = self.wait_for_message(
                "diff_share",
                extra_check=lambda d: d.get("guesser") == guesser
            )
            if data:
                sender = data["from"]
                all_dx[sender] = data["d_x"]
                all_dy[sender] = data["d_y"]

        total_dx = mod(sum(all_dx.values()))
        total_dy = mod(sum(all_dy.values()))

        guessed = (total_dx == 0 and total_dy == 0)

        if guessed:
            print(f"[{self.nickname}] ✅ {guesser} УГАДАЛ точку Q!")
        else:
            print(f"[{self.nickname}] ❌ {guesser} не угадал.")

        return guessed

    def play(self, expected_players):
        self.connect_and_wait(expected_players)

        # Пауза чтобы все точно подключились
        time.sleep(2)

        # Синхронизация
        self.sync_barrier("game_start")

        print(f"\n{'='*50}")
        print(f"[{self.nickname}] НАЧИНАЕМ ИГРУ! Поле {self.field_size}x{self.field_size}")
        print(f"{'='*50}\n")

        self.generate_secret_point()
        self.sync_barrier("point_generated")

        round_num = 0
        winner = None

        while winner is None:
            for player in self.all_players:
                round_num += 1
                print(f"\n--- Раунд {round_num}: ходит {player} ---")

                if player == self.nickname:
                    guess_x = int(input(f"Введите x (1-{self.field_size}): "))
                    guess_y = int(input(f"Введите y (1-{self.field_size}): "))

                    msg = json.dumps({
                        "type": "start_check",
                        "guesser": self.nickname
                    })
                    self.conn.send_to(self.peers, msg)
                    time.sleep(0.5)

                    guessed = self.check_guess(self.nickname, guess_x, guess_y)
                else:
                    print(f"[{self.nickname}] Ожидаю ход {player}...")
                    self.wait_for_message(
                        "start_check",
                        extra_check=lambda d: d.get("guesser") == player
                    )
                    guessed = self.check_guess(player)

                self.sync_barrier(f"round_{round_num}")

                if guessed:
                    winner = player
                    break

        print(f"\n{'='*50}")
        print(f"🏆 ПОБЕДИТЕЛЬ: {winner}!")
        print(f"{'='*50}")
        self.conn.close()