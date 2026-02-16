# network.py

import socket
import time
from config import SERVER_HOST, SERVER_PORT


class RepeaterConnection:
    def __init__(self, host=SERVER_HOST, port=SERVER_PORT, nickname=None):
        self.host = host
        self.port = port
        self.nickname = nickname
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buffer = ""
        self.message_queue = []

    def connect(self):
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(30)
        data = self._recv_until("Pick nickname: ")
        print(f"[NET] Получено: {data}")
        self.sock.sendall(f"{self.nickname}\n".encode())
        print(f"[NET] Отправлен никнейм: {self.nickname}")
        time.sleep(1)
        data = self._recv_all_available()
        print(f"[NET] Ответ сервера:\n{data}")

    def send_to(self, recipients, data):
        if isinstance(recipients, list):
            recipients = ",".join(recipients)
        data_clean = data.strip()
        msg = f"send {recipients} {data_clean}\n"
        self.sock.sendall(msg.encode())

    def recv_message(self, timeout=60):
        """Получить одну строку из сети."""
        if self.message_queue:
            return self.message_queue.pop(0)

        self.sock.settimeout(timeout)
        deadline = time.time() + timeout

        while time.time() < deadline:
            # Проверяем буфер
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                line = line.strip()
                if line:
                    return line

            remaining = max(0.1, deadline - time.time())
            self.sock.settimeout(remaining)
            try:
                chunk = self.sock.recv(4096).decode()
                if not chunk:
                    break
                self.buffer += chunk
            except socket.timeout:
                break

        # Последняя проверка буфера
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.strip()
            if line:
                return line

        return None

    def _recv_until(self, marker):
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