# player.py

import json
import random
import time
from config import FIELD_SIZE, PRIME
from crypto_utils import generate_additive_shares, mod
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
            self.peers = self.conn.get_peers_once()
            current = len(self.peers) + 1
            print(f"[{self.nickname}] Подключено: {current}/{expected_players}")
            if current >= expected_players:
                break
            time.sleep(3)

        self.all_players = sorted(self.peers + [self.nickname])
        self.my_index = self.all_players.index(self.nickname)
        self.num_parties = len(self.all_players)
        print(f"[{self.nickname}] Все игроки: {self.all_players}")

    def wait_for_message(self, msg_type, extra_check=None, timeout=300):
        deadline = time.time() + timeout

        # Проверяем очередь
        new_queue = []
        for item in self.conn.message_queue:
            try:
                data = json.loads(item)
                if data.get("type") == msg_type:
                    if extra_check is None or extra_check(data):
                        self.conn.message_queue = new_queue + self.conn.message_queue[self.conn.message_queue.index(item)+1:]
                        return data
            except json.JSONDecodeError:
                pass
            new_queue.append(item)

        while time.time() < deadline:
            remaining = max(1, deadline - time.time())
            raw = self.conn.recv_message(timeout=remaining)
            if not raw:
                continue
            try:
                data = json.loads(raw)
                if data.get("type") == msg_type:
                    if extra_check is None or extra_check(data):
                        return data
                self.conn.message_queue.append(raw)
            except json.JSONDecodeError:
                pass
        return None

    def collect_messages(self, msg_type, count, extra_check=None, timeout=300):
        results = []
        deadline = time.time() + timeout
        while len(results) < count and time.time() < deadline:
            remaining = max(1, deadline - time.time())
            data = self.wait_for_message(msg_type, extra_check, timeout=remaining)
            if data:
                results.append(data)
        return results

    def sync_barrier(self, barrier_name):
        print(f"[{self.nickname}] Барьер '{barrier_name}' — отправляю...")
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
                print(f"[{self.nickname}] Барьер '{barrier_name}' — получил от {data['from']}")
        print(f"[{self.nickname}] Барьер '{barrier_name}' ОК")

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
                print(f"[{self.nickname}] Отправил долю для {player}")

        msgs = self.collect_messages("share", self.num_parties - 1)
        for data in msgs:
            sender = data["from"]
            self.shares_x[sender] = data["share_x"]
            self.shares_y[sender] = data["share_y"]
            print(f"[{self.nickname}] Получена доля от {sender}")

        self.my_total_share_x = mod(sum(self.shares_x.values()))
        self.my_total_share_y = mod(sum(self.shares_y.values()))
        print(f"[{self.nickname}] Точка Q сгенерирована")

    def check_guess(self, guesser, guess_x=None, guess_y=None):
        is_me = (guesser == self.nickname)

        if is_me:
            print(f"[{self.nickname}] Угадываю: ({guess_x}, {guess_y})")
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

        msgs = self.collect_messages(
            "diff_share",
            self.num_parties - 1,
            extra_check=lambda d: d.get("guesser") == guesser
        )
        for data in msgs:
            all_dx[data["from"]] = data["d_x"]
            all_dy[data["from"]] = data["d_y"]

        total_dx = mod(sum(all_dx.values()))
        total_dy = mod(sum(all_dy.values()))
        guessed = (total_dx == 0 and total_dy == 0)

        if guessed:
            print(f"[{self.nickname}] ✅ {guesser} УГАДАЛ!")
        else:
            print(f"[{self.nickname}] ❌ {guesser} не угадал")
        return guessed

    def play(self, expected_players):
        self.connect_and_wait(expected_players)

        print(f"[{self.nickname}] Жду 3 сек перед стартом...")
        time.sleep(3)

        self.sync_barrier("game_start")

        print(f"\n{'='*50}")
        print(f"[{self.nickname}] ИГРА! Поле {self.field_size}x{self.field_size}")
        print(f"{'='*50}\n")

        self.generate_secret_point()
        self.sync_barrier("point_generated")

        round_num = 0
        winner = None

        while winner is None:
            for player in self.all_players:
                round_num += 1
                print(f"\n--- Раунд {round_num}: {player} ---")

                if player == self.nickname:
                    guess_x = int(input(f"x (1-{self.field_size}): "))
                    guess_y = int(input(f"y (1-{self.field_size}): "))

                    msg = json.dumps({"type": "start_check", "guesser": self.nickname})
                    self.conn.send_to(self.peers, msg)
                    time.sleep(0.5)
                    guessed = self.check_guess(self.nickname, guess_x, guess_y)
                else:
                    print(f"[{self.nickname}] Жду ход {player}...")
                    self.wait_for_message(
                        "start_check",
                        extra_check=lambda d: d.get("guesser") == player
                    )
                    guessed = self.check_guess(player)

                self.sync_barrier(f"round_{round_num}")

                if guessed:
                    winner = player
                    break

        print(f"\n🏆 ПОБЕДИТЕЛЬ: {winner}!")
        self.conn.close()