# network.py

import socket
import time
import json
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
        """Отправить JSON-данные получателям. Добавляем маркер конца ||"""
        if isinstance(recipients, list):
            recipients = ",".join(recipients)
        data_clean = data.strip()
        # Добавляем маркер || чтобы получатель мог разделить сообщения
        msg = f"send {recipients} {data_clean}||\n"
        self.sock.sendall(msg.encode())

    def recv_message(self, timeout=60):
        """Получить одно JSON-сообщение, разделённое маркером ||"""
        # Сначала проверяем очередь
        if self.message_queue:
            return self.message_queue.pop(0)

        deadline = time.time() + timeout

        while time.time() < deadline:
            # Ищем маркер || в буфере
            self._extract_messages()
            if self.message_queue:
                return self.message_queue.pop(0)

            remaining = max(0.1, deadline - time.time())
            self.sock.settimeout(remaining)
            try:
                chunk = self.sock.recv(4096).decode()
                if not chunk:
                    break
                self.buffer += chunk
            except socket.timeout:
                break

        # Последняя попытка
        self._extract_messages()
        if self.message_queue:
            return self.message_queue.pop(0)

        return None

    def _extract_messages(self):
        """Извлечь все JSON-сообщения из буфера по маркеру ||"""
        while "||" in self.buffer:
            idx = self.buffer.index("||")
            raw = self.buffer[:idx].strip()
            self.buffer = self.buffer[idx + 2:]

            if raw.startswith("{"):
                self.message_queue.append(raw)
            # Иначе — серверное сообщение, игнорируем

    def get_peers_once(self):
        """Один запрос списка подключённых."""
        self.sock.sendall(b"print\n")
        time.sleep(1.5)
        raw = self._recv_all_available()

        peers = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # JSON-сообщения сохраняем
            if "||" in line:
                parts = line.split("||")
                for part in parts:
                    part = part.strip()
                    if part.startswith("{"):
                        self.message_queue.append(part)
            elif line.startswith("{"):
                self.message_queue.append(line)
            elif "available connections" not in line:
                peers.append(line)
        return peers

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