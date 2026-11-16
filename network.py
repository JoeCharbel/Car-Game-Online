"""
P2P Networking module for the online car game.
Uses TCP sockets with length-prefixed JSON messages.
"""

import socket
import threading
import json
import struct
import queue


def send_msg(sock, obj):
    """Send a JSON-serializable object with a 4-byte length prefix."""
    try:
        data = json.dumps(obj).encode('utf-8')
        sock.sendall(struct.pack('!I', len(data)) + data)
        return True
    except (ConnectionError, OSError):
        return False


def recv_msg(sock):
    """Receive a length-prefixed JSON message. Returns None on disconnect."""
    try:
        raw_len = _recv_exactly(sock, 4)
        if not raw_len:
            return None
        msg_len = struct.unpack('!I', raw_len)[0]
        if msg_len > 10_000_000:  # sanity limit 10MB
            return None
        raw_data = _recv_exactly(sock, msg_len)
        if not raw_data:
            return None
        return json.loads(raw_data.decode('utf-8'))
    except (ConnectionError, OSError, json.JSONDecodeError):
        return None


def _recv_exactly(sock, n):
    """Receive exactly n bytes from socket."""
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


class GameServer:
    """
    TCP game server (runs on the host player's machine).
    Manages connections, relays messages, and maintains player registry.
    """

    def __init__(self, port=5555):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = {}        # player_id -> socket
        self.client_info = {}    # player_id -> {name, ready, alive, color_idx, ...}
        self.incoming = queue.Queue()  # (player_id, message_dict)
        self.next_id = 1         # 0 is reserved for host
        self.running = False
        self._lock = threading.Lock()

    def start(self):
        """Start the server listening for connections."""
        self.sock.bind(('0.0.0.0', self.port))
        self.sock.listen(5)
        self.sock.settimeout(1.0)
        self.running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def stop(self):
        """Shut down the server and close all connections."""
        self.running = False
        with self._lock:
            for pid, sock in list(self.clients.items()):
                try:
                    sock.close()
                except Exception:
                    pass
            self.clients.clear()
        try:
            self.sock.close()
        except Exception:
            pass

    def _accept_loop(self):
        """Accept new client connections."""
        while self.running:
            try:
                conn, addr = self.sock.accept()
                conn.settimeout(5.0)
                # Wait for the JOIN message
                msg = recv_msg(conn)
                if msg and msg.get('type') == 'JOIN':
                    with self._lock:
                        pid = self.next_id
                        self.next_id += 1
                        self.clients[pid] = conn
                        self.client_info[pid] = {
                            'name': msg.get('name', f'Player {pid}'),
                            'ready': False,
                            'alive': True,
                            'color_idx': pid,
                        }
                    # Send assignment
                    send_msg(conn, {'type': 'ASSIGN_ID', 'player_id': pid})
                    conn.settimeout(None)  # blocking recv after handshake
                    # Start receive thread for this client
                    t = threading.Thread(target=self._client_recv, args=(pid, conn), daemon=True)
                    t.start()
                    # Notify about new player
                    self.incoming.put((pid, {'type': 'PLAYER_JOINED',
                                             'player_id': pid,
                                             'name': msg.get('name', f'Player {pid}')}))
                else:
                    conn.close()
            except socket.timeout:
                continue
            except OSError:
                if self.running:
                    continue
                break

    def _client_recv(self, player_id, conn):
        """Receive messages from a specific client."""
        while self.running:
            msg = recv_msg(conn)
            if msg is None:
                # Client disconnected
                self.incoming.put((player_id, {'type': 'PLAYER_DISCONNECTED',
                                                'player_id': player_id}))
                with self._lock:
                    self.clients.pop(player_id, None)
                    self.client_info.pop(player_id, None)
                try:
                    conn.close()
                except Exception:
                    pass
                return
            msg['_from'] = player_id
            self.incoming.put((player_id, msg))

    def broadcast(self, msg, exclude=None):
        """Send a message to all connected clients."""
        with self._lock:
            for pid, sock in list(self.clients.items()):
                if exclude and pid in exclude:
                    continue
                if not send_msg(sock, msg):
                    # Client is gone
                    self.clients.pop(pid, None)
                    self.client_info.pop(pid, None)

    def send_to(self, player_id, msg):
        """Send a message to a specific player."""
        with self._lock:
            sock = self.clients.get(player_id)
            if sock:
                if not send_msg(sock, msg):
                    self.clients.pop(player_id, None)
                    self.client_info.pop(player_id, None)

    def get_messages(self):
        """Get all pending incoming messages (non-blocking)."""
        messages = []
        while True:
            try:
                messages.append(self.incoming.get_nowait())
            except queue.Empty:
                break
        return messages


class GameClient:
    """
    TCP game client (runs on joining players' machines).
    Connects to the host, sends/receives JSON messages.
    """

    def __init__(self):
        self.sock = None
        self.player_id = None
        self.incoming = queue.Queue()
        self.connected = False
        self._recv_thread = None

    def connect(self, host, port, name):
        """Connect to a game server. Returns True on success."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((host, port))

            # Send JOIN
            send_msg(self.sock, {'type': 'JOIN', 'name': name})

            # Wait for ID assignment
            msg = recv_msg(self.sock)
            if msg and msg.get('type') == 'ASSIGN_ID':
                self.player_id = msg['player_id']
                self.sock.settimeout(None)  # blocking recv after handshake
                self.connected = True
                self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
                self._recv_thread.start()
                return True
            else:
                self.sock.close()
                return False
        except (ConnectionError, OSError, socket.timeout):
            if self.sock:
                self.sock.close()
            return False

    def disconnect(self):
        """Disconnect from the server."""
        self.connected = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

    def send(self, msg):
        """Send a message to the server."""
        if self.connected and self.sock:
            if not send_msg(self.sock, msg):
                self.connected = False

    def _recv_loop(self):
        """Background thread receiving messages from the server."""
        while self.connected:
            msg = recv_msg(self.sock)
            if msg is None:
                self.connected = False
                self.incoming.put({'type': 'DISCONNECTED'})
                return
            self.incoming.put(msg)

    def get_messages(self):
        """Get all pending incoming messages (non-blocking)."""
        messages = []
        while True:
            try:
                messages.append(self.incoming.get_nowait())
            except queue.Empty:
                break
        return messages
