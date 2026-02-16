# network.py

import socket
import time
from config import SERVER_HOST, SERVER_PORT


class RepeaterConnection:
    """Класс для работы с сервером-ретранслятором."""

    def __init__(self, host=SERVER_HOST, port=SERVER_PORT, nickname=None):
        self.host = host
        self.port = port
        self.nickname = nickname
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buffer = ""

    def connect(self):
        """Подключиться к ретранслятору и зарегистрировать никнейм."""
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(30)

        # Ждём приглашение "Pick nickname: "
        data = self._recv_until("Pick nickname: ")
        print(f"[NET] Получено: {data}")

        # Отправляем никнейм
        self.sock.sendall(f"{self.nickname}\n".encode())
        print(f"[NET] Отправлен никнейм: {self.nickname}")

        # Читаем список подключённых
        time.sleep(1)
        data = self._recv_all_available()
        print(f"[NET] Ответ сервера:\n{data}")

    def send_to(self, recipients, data):
        """
        Отправить данные указанным получателям.
        recipients: список никнеймов или строка с никнеймами через запятую
        data: строка данных
        """
        if isinstance(recipients, list):
            recipients = ",".join(recipients)
        msg = f"send {recipients} {data}\n"
        self.sock.sendall(msg.encode())
        print(f"[NET] Отправлено -> {recipients}: {data.strip()}")

    def get_peers(self):
        """Получить список подключённых участников."""
        self.sock.sendall(b"print\n")
        time.sleep(0.5)
        data = self._recv_all_available()
        lines = data.strip().split("\n")
        peers = []
        for line in lines:
            line = line.strip()
            if line and "available connections" not in line:
                peers.append(line)
        return peers

    def recv_message(self, timeout=60):
        """
        Получить одно сообщение (строку, заканчивающуюся \n).
        """
        self.sock.settimeout(timeout)
        while "\n" not in self.buffer:
            try:
                chunk = self.sock.recv(4096).decode()
                if not chunk:
                    break
                self.buffer += chunk
            except socket.timeout:
                break

        if "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            return line.strip()
        
        # Если нет \n, вернём всё что есть
        result = self.buffer.strip()
        self.buffer = ""
        return result

    def recv_messages(self, expected_count, timeout=60):
        """Получить expected_count сообщений."""
        messages = []
        deadline = time.time() + timeout
        while len(messages) < expected_count and time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            msg = self.recv_message(timeout=remaining)
            if msg:
                messages.append(msg)
        return messages

    def _recv_until(self, marker):
        """Читаем до появления marker в буфере."""
        while marker not in self.buffer:
            chunk = self.sock.recv(4096).decode()
            if not chunk:
                break
            self.buffer += chunk
        idx = self.buffer.find(marker)
        if idx != -1:
            result = self.buffer[:idx + len(marker)]
            self.buffer = self.buffer[idx + len(marker):]
            return result
        result = self.buffer
        self.buffer = ""
        return result

    def _recv_all_available(self):
        """Прочитать всё доступное из сокета."""
        self.sock.settimeout(2)
        data = ""
        try:
            while True:
                chunk = self.sock.recv(4096).decode()
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        self.sock.settimeout(30)
        return data

    def close(self):
        self.sock.close()