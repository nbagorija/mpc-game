#!/usr/bin/env -S python3
#-*- coding:utf-8 -*-

from sys import argv
import os
import socket
import socketserver
import threading
import time
import re

available_connections = {}
connections_lock = threading.Lock()

def is_socket_closed(sock: socket.socket) -> bool:
    try:
        data = sock.recv(16, socket.MSG_DONTWAIT | socket.MSG_PEEK)
        if len(data) == 0:
            return True
    except BlockingIOError:
        return False
    except ConnectionResetError:
        return True
    except Exception as e:
        return False
    return False

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def print_available_connections(self):
        with connections_lock:
            conn_count = len(available_connections)-1
            conn_list = available_connections.keys()
        self.request.sendall("{} available connections:\n".format(conn_count).encode())
        for key in conn_list:
            if key != self.nickname:
                self.request.sendall("{}\n".format(key).encode())
    
    def setup(self):
        try:
            self.request.settimeout(3600)  # 1 час таймаут
            self.max_recv_size = 1024
            while True:
                self.request.sendall("Pick nickname: ".encode())
                self.nickname = self.request.recv(self.max_recv_size).decode().strip()
                if re.fullmatch("[a-z0-9_]+", self.nickname, flags=re.IGNORECASE):
                    with connections_lock:
                        used = self.nickname in available_connections.keys()
                    if not used:
                        break
                    else:
                        self.request.sendall("Nickname is already used\n".encode())
                else:
                    self.request.sendall("Nickname must contain only characters A-Za-z0-9_\n".encode())
            with connections_lock:
                available_connections[self.nickname] = self
            self.print_available_connections()
            self.commands = [""]
        except Exception as e:
            error = getattr(e, 'message', repr(e))
            self.request.sendall("Error: {}\n".format(error).encode())
            return

    def handle_commands(self):
        while len(self.commands) > 1:
            command = self.commands[0].split(" ")
            if command[0] == "print":
                self.print_available_connections()
            elif command[0] == "send":
                if len(command) < 3:
                    self.request.sendall("Send command usage: send nickname1,nickname2,... data\n".encode())
                else:
                    nicks = command[1].split(",")
                    data = self.commands[0]
                    data = data[data.find(" ") + 1:]
                    data = data[data.find(" ") + 1:]
                    with connections_lock:
                        conns = [available_connections[nick] for nick in nicks if (nick in available_connections.keys() and nick != self.nickname)]
                    for sock in conns:
                        sock.request.sendall(data.encode())
            else:
                self.request.sendall("Unknown command: {}\n".format(command[0]).encode())
            self.commands.pop(0)

    def handle(self):
        try:
            while True:
                s = self.request.recv(self.max_recv_size).decode().split("\n")
                self.commands[-1] = self.commands[-1] + s[0]
                self.commands += s[1:]
                self.handle_commands()
                if is_socket_closed(self.request):
                    return
        except Exception as e:
            error = getattr(e, 'message', repr(e))
            self.request.sendall("Error: {}\n".format(error).encode())
            return

    def finish(self):
        try:
            with connections_lock:
                available_connections.pop(self.nickname)
        except Exception as e:
            error = getattr(e, 'message', repr(e))
            self.request.sendall("Error: {}\n".format(error).encode())
            return    

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


def start_server(port=0):
    with ThreadedTCPServer(('0.0.0.0', port), ThreadedTCPRequestHandler) as server:
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        while True:
            if threading.active_count() > 75:
                raise Exception()
            time.sleep(100)

        server_thread.join()

def main():
    if len(argv) < 2:
        print("Usage: %s port" % (argv[0]))
        return 0
    start_server(port=int(argv[1]))
    return 0

if __name__ == "__main__":
    main()