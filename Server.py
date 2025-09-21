import socket
import threading
import json
import time
import os
from enum import Enum
from datetime import datetime

class PlayerRole(Enum):
    BLACK = 1
    WHITE = 2
    SPECTATOR = 3

class GomokuServer:
    def __init__(self, host='localhost', port=8888):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = {}
        self.players = {}
        self.spectators = []
        self.board = [[' ' for _ in range(15)] for _ in range(15)]
        self.current_turn = PlayerRole.BLACK
        self.game_started = False
        self.move_history = []
        self.chat_history = []
        self.game_id = None
        self.lock = threading.Lock()
        self.user_counter = 0
        self.banned_ips = self.load_banned_ips()
        self.usernames = set()
        self.last_move_time = {}
        
        if not os.path.exists("replays"):
            os.makedirs("replays")
        if not os.path.exists("chat_logs"):
            os.makedirs("chat_logs")

    def load_banned_ips(self):
        try:
            if os.path.exists("banned.json"):
                with open("banned.json", "r") as f:
                    banned_data = json.load(f)
                    if isinstance(banned_data, list):
                        return banned_data
                    else:
                        return list(banned_data.keys())
            else:
                with open("banned.json", "w") as f:
                    json.dump([], f)
                return []
        except Exception as e:
            print(f"加载封禁列表失败: {e}")
            return []

    def save_banned_ips(self):
        try:
            with open("banned.json", "w") as f:
                json.dump(self.banned_ips, f)
        except Exception as e:
            print(f"保存封禁列表失败: {e}")

    def is_ip_banned(self, ip):
        return ip in self.banned_ips

    def ban_ip(self, ip, duration_minutes=10):
        if ip not in self.banned_ips:
            self.banned_ips.append(ip)
            self.save_banned_ips()
            print(f"已封禁IP: {ip}, 时长: {duration_minutes}分钟")
            
            timer = threading.Timer(duration_minutes * 60, self.unban_ip, [ip])
            timer.daemon = True
            timer.start()

    def unban_ip(self, ip):
        if ip in self.banned_ips:
            self.banned_ips.remove(ip)
            self.save_banned_ips()
            print(f"已解封IP: {ip}")

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"服务器已启动，监听地址: {self.host}:{self.port}")

        while True:
            client_socket, addr = self.server_socket.accept()
            client_ip = addr[0]
            
            if self.is_ip_banned(client_ip):
                print(f"拒绝被封禁IP的连接: {client_ip}")
                try:
                    ban_msg = {"type": "banned", "message": "您的IP已被封禁，无法连接服务器"}
                    client_socket.send(json.dumps(ban_msg).encode())
                    time.sleep(1)
                except:
                    pass
                client_socket.close()
                continue
                
            print(f"新连接: {addr}")
            client_handler = threading.Thread(target=self.handle_client, args=(client_socket, addr))
            client_handler.daemon = True
            client_handler.start()

    def handle_client(self, client_socket, addr):
        client_ip = addr[0]
        
        try:
            data = client_socket.recv(1024).decode()
            login_info = json.loads(data)
            
            if login_info["type"] != "login" or "username" not in login_info:
                client_socket.send(json.dumps({"type": "error", "message": "请先发送用户名"}).encode())
                client_socket.close()
                return
                
            username = login_info["username"]
            is_admin = login_info.get("is_admin", False)
            
            with self.lock:
                if username in self.usernames:
                    client_socket.send(json.dumps({"type": "error", "message": "用户名已存在，请选择其他用户名"}).encode())
                    client_socket.close()
                    return
                
                self.usernames.add(username)
                
            user_id = f"user_{self.user_counter}"
            self.user_counter += 1
            
            with self.lock:
                self.clients[client_socket] = {
                    "username": username,
                    "user_id": user_id,
                    "role": None,
                    "address": client_ip,
                    "is_admin": is_admin
                }
            
            with self.lock:
                if len(self.players) < 2 and not is_admin:
                    if len(self.players) == 0:
                        role = PlayerRole.BLACK
                        self.players[client_socket] = role
                        welcome_msg = {"type": "role", "role": "BLACK", "username": username}
                    else:
                        role = PlayerRole.WHITE
                        self.players[client_socket] = role
                        welcome_msg = {"type": "role", "role": "WHITE", "username": username}
                        self.game_started = True
                        self.game_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    self.clients[client_socket]["role"] = role
                    self.last_move_time[client_socket] = 0
                    client_socket.send(json.dumps(welcome_msg).encode())
                    
                    join_msg = {"type": "user_joined", "username": username, "role": role.name, "address": client_ip}
                    self.broadcast(join_msg, include_spectators=True)
                    
                    if self.game_started:
                        self.broadcast({"type": "game_start", "message": "游戏开始! 黑棋先行"}, include_spectators=True)
                        client_socket.send(json.dumps({"type": "board", "board": self.board}).encode())
                        client_socket.send(json.dumps({"type": "move_history", "history": self.move_history}).encode())
                        client_socket.send(json.dumps({"type": "chat_history", "history": self.chat_history}).encode())
                else:
                    if is_admin:
                        role = None
                        welcome_msg = {"type": "role", "role": "ADMIN", "username": username}
                        client_socket.send(json.dumps(welcome_msg).encode())
                        
                        client_socket.send(json.dumps({"type": "board", "board": self.board}).encode())
                        client_socket.send(json.dumps({"type": "move_history", "history": self.move_history}).encode())
                        client_socket.send(json.dumps({"type": "chat_history", "history": self.chat_history}).encode())
                        
                        self.send_user_list(client_socket)
                    else:
                        role = PlayerRole.SPECTATOR
                        self.spectators.append(client_socket)
                        self.clients[client_socket]["role"] = role
                        welcome_msg = {"type": "role", "role": "SPECTATOR", "username": username}
                        client_socket.send(json.dumps(welcome_msg).encode())
                        client_socket.send(json.dumps({"type": "board", "board": self.board}).encode())
                        client_socket.send(json.dumps({"type": "move_history", "history": self.move_history}).encode())
                        client_socket.send(json.dumps({"type": "chat_history", "history": self.chat_history}).encode())
                        
                        join_msg = {"type": "user_joined", "username": username, "role": "SPECTATOR", "address": client_ip}
                        self.broadcast(join_msg, include_spectators=True)
        
        except Exception as e:
            print(f"登录错误: {e}")
            with self.lock:
                if username in self.usernames:
                    self.usernames.remove(username)
            client_socket.close()
            return
        
        buffer = ""
        try:
            while True:
                data = client_socket.recv(1024).decode()
                if not data:
                    break
                
                buffer += data
                while buffer:
                    try:
                        message, idx = self.parse_json(buffer)
                        buffer = buffer[idx:]
                        
                        role = self.clients[client_socket]["role"]
                        is_admin = self.clients[client_socket]["is_admin"]
                        self.process_message(client_socket, message, role, is_admin)
                        
                    except json.JSONDecodeError:
                        break
                    except ValueError:
                        buffer = ""
                        break
                        
        except Exception as e:
            print(f"客户端错误: {e}")
        finally:
            with self.lock:
                username = self.clients[client_socket]["username"]
                if username in self.usernames:
                    self.usernames.remove(username)
                    
                if client_socket in self.players:
                    del self.players[client_socket]
                if client_socket in self.spectators:
                    self.spectators.remove(client_socket)
                if client_socket in self.clients:
                    del self.clients[client_socket]
                if client_socket in self.last_move_time:
                    del self.last_move_time[client_socket]
                client_socket.close()
                
                leave_msg = {"type": "user_left", "username": username}
                self.broadcast(leave_msg, include_spectators=True)
                print(f"客户端断开连接: {username}")

    def parse_json(self, data):
        try:
            message = json.loads(data)
            return message, len(data)
        except json.JSONDecodeError as e:
            if e.msg == "Extra data":
                message = json.loads(data[:e.pos])
                return message, e.pos
            else:
                raise

    def process_message(self, client_socket, message, role, is_admin):
        if message["type"] == "move":
            if role == PlayerRole.SPECTATOR or role is None:
                return
                
            if role != self.current_turn:
                error_msg = {"type": "error", "message": "还没轮到你下棋"}
                client_socket.send(json.dumps(error_msg).encode())
                return
                
            x, y = message["x"], message["y"]
            
            current_time = time.time()
            if current_time - self.last_move_time[client_socket] < 0.1:
                self.handle_cheating(client_socket, "移动速度过快，疑似使用机器人")
                return
                
            self.last_move_time[client_socket] = current_time
            
            if self.is_valid_move(x, y):
                piece = 'B' if role == PlayerRole.BLACK else 'W'
                self.board[x][y] = piece
                
                move_record = {
                    "x": x, 
                    "y": y, 
                    "piece": piece,
                    "username": self.clients[client_socket]["username"],
                    "timestamp": time.time()
                }
                self.move_history.append(move_record)
                
                move_msg = {
                    "type": "move_made", 
                    "x": x, 
                    "y": y, 
                    "piece": piece,
                    "username": self.clients[client_socket]["username"]
                }
                self.broadcast(move_msg, include_spectators=True)
                
                if self.check_win(x, y):
                    winner = "黑棋" if role == PlayerRole.BLACK else "白棋"
                    winner_name = self.clients[client_socket]["username"]
                    win_msg = {
                        "type": "game_over", 
                        "winner": winner, 
                        "winner_name": winner_name,
                        "message": f"{winner}({winner_name})获胜!"
                    }
                    self.broadcast(win_msg, include_spectators=True)
                    
                    self.save_game_replay(winner_name)
                    self.reset_game()
                else:
                    self.current_turn = PlayerRole.WHITE if self.current_turn == PlayerRole.BLACK else PlayerRole.BLACK
                    turn_msg = {"type": "turn", "turn": "BLACK" if self.current_turn == PlayerRole.BLACK else "WHITE"}
                    self.broadcast(turn_msg, include_spectators=True)
        
        elif message["type"] == "chat":
            username = self.clients[client_socket]["username"]
            
            if is_admin:
                user_role = "管理员"
            else:
                user_role = "黑棋" if role == PlayerRole.BLACK else "白棋" if role == PlayerRole.WHITE else "观战者"
            
            chat_record = {
                "username": username,
                "role": user_role,
                "message": message["message"],
                "timestamp": time.time(),
                "audience": "spectators" if role == PlayerRole.SPECTATOR else "all"
            }
            self.chat_history.append(chat_record)
            
            if role == PlayerRole.SPECTATOR and not is_admin:
                chat_msg = {
                    "type": "chat", 
                    "message": message["message"],
                    "username": username,
                    "role": user_role,
                    "audience": "spectators"
                }
                for spec in self.spectators:
                    if spec != client_socket:
                        spec.send(json.dumps(chat_msg).encode())
            else:
                chat_msg = {
                    "type": "chat", 
                    "message": message["message"],
                    "username": username,
                    "role": user_role,
                    "audience": "all"
                }
                self.broadcast(chat_msg, include_spectators=True)
        
        elif message["type"] == "replay_request":
            history_msg = {"type": "move_history", "history": self.move_history}
            client_socket.send(json.dumps(history_msg).encode())
        
        elif message["type"] == "admin_command":
            if not is_admin:
                return
                
            if message["command"] == "ban_ip" and "target" in message:
                self.ban_ip(message["target"])
                response = {"type": "admin_response", "message": f"已封禁IP: {message['target']}"}
                client_socket.send(json.dumps(response).encode())
            
            elif message["command"] == "unban_ip" and "target" in message:
                self.unban_ip(message["target"])
                response = {"type": "admin_response", "message": f"已解封IP: {message['target']}"}
                client_socket.send(json.dumps(response).encode())
            
            elif message["command"] == "force_end" and "reason" in message:
                reason = message["reason"]
                end_msg = {
                    "type": "game_force_end", 
                    "message": f"管理员强制结束游戏，理由: {reason}",
                    "reason": reason
                }
                self.broadcast(end_msg, include_spectators=True)
                
                self.save_game_replay("管理员强制结束")
                self.reset_game()
            
            elif message["command"] == "broadcast" and "message" in message:
                broadcast_msg = {
                    "type": "broadcast", 
                    "message": message["message"],
                    "from": "管理员"
                }
                self.broadcast(broadcast_msg, include_spectators=True)
            
            elif message["command"] == "get_user_list":
                self.send_user_list(client_socket)
            
            elif message["command"] == "kick_user" and "username" in message:
                target_username = message["username"]
                for sock, info in list(self.clients.items()):
                    if info["username"] == target_username:
                        try:
                            kick_msg = {"type": "kicked", "message": "您已被管理员踢出服务器"}
                            sock.send(json.dumps(kick_msg).encode())
                            time.sleep(0.1)
                            sock.close()
                        except:
                            pass
                        break

    def handle_cheating(self, cheater_socket, reason):
        cheater_info = self.clients[cheater_socket]
        cheater_ip = cheater_info["address"]
        cheater_name = cheater_info["username"]
        
        self.ban_ip(cheater_ip)
        
        winner_socket = None
        winner_name = "系统"
        for sock, role in self.players.items():
            if sock != cheater_socket:
                winner_socket = sock
                winner_name = self.clients[sock]["username"]
                break
        
        cheat_msg = {
            "type": "cheat_detected",
            "cheater": cheater_name,
            "winner": winner_name,
            "reason": reason
        }
        self.broadcast(cheat_msg, include_spectators=True)
        
        try:
            cheat_notice = {"type": "cheating", "message": f"您因作弊被踢出服务器: {reason}"}
            cheater_socket.send(json.dumps(cheat_notice).encode())
            time.sleep(0.1)
            cheater_socket.close()
        except:
            pass
        
        with self.lock:
            if cheater_socket in self.players:
                del self.players[cheater_socket]
            if cheater_socket in self.clients:
                del self.clients[cheater_socket]
            if cheater_socket in self.last_move_time:
                del self.last_move_time[cheater_socket]
            if cheater_info["username"] in self.usernames:
                self.usernames.remove(cheater_info["username"])
        
        if self.game_started and winner_socket:
            win_msg = {
                "type": "game_over", 
                "winner": "黑棋" if self.players[winner_socket] == PlayerRole.BLACK else "白棋", 
                "winner_name": winner_name,
                "message": f"由于对手作弊，{winner_name}获胜!"
            }
            self.broadcast(win_msg, include_spectators=True)
            
            self.save_game_replay(winner_name)
            self.reset_game()

    def send_user_list(self, client_socket):
        user_list = []
        for sock, info in self.clients.items():
            if info["role"]:
                role_name = "黑棋" if info["role"] == PlayerRole.BLACK else "白棋" if info["role"] == PlayerRole.WHITE else "观战者"
            else:
                role_name = "管理员" if info["is_admin"] else "未知"
                
            user_list.append({
                "username": info["username"],
                "role": role_name,
                "address": info["address"],
                "is_admin": info["is_admin"]
            })
        
        user_list_msg = {"type": "user_list", "users": user_list}
        client_socket.send(json.dumps(user_list_msg).encode())

    def broadcast(self, message, include_spectators=False):
        data = json.dumps(message).encode()
        
        if include_spectators:
            for client in list(self.clients.keys()):
                try:
                    client.send(data)
                except:
                    pass
        else:
            for player in list(self.players.keys()):
                try:
                    player.send(data)
                except:
                    pass

    def save_game_replay(self, winner):
        if not self.game_id:
            return
            
        replay_data = {
            "game_id": self.game_id,
            "start_time": self.move_history[0]["timestamp"] if self.move_history else time.time(),
            "end_time": time.time(),
            "winner": winner,
            "moves": self.move_history,
            "board_size": 15
        }
        
        with open(f"replays/{self.game_id}.json", "w") as f:
            json.dump(replay_data, f, indent=2)
        
        chat_data = {
            "game_id": self.game_id,
            "chats": self.chat_history
        }
        
        with open(f"chat_logs/{self.game_id}.json", "w") as f:
            json.dump(chat_data, f, indent=2)
        
        print(f"已保存游戏回放: {self.game_id}")

    def is_valid_move(self, x, y):
        return 0 <= x < 15 and 0 <= y < 15 and self.board[x][y] == ' '

    def check_win(self, x, y):
        piece = self.board[x][y]
        directions = [
            [(0, 1), (0, -1)],
            [(1, 0), (-1, 0)],
            [(1, 1), (-1, -1)],
            [(1, -1), (-1, 1)]
        ]
        
        for dir_pair in directions:
            count = 1
            
            for dx, dy in dir_pair:
                nx, ny = x, y
                for _ in range(4):
                    nx, ny = nx + dx, ny + dy
                    if 0 <= nx < 15 and 0 <= ny < 15 and self.board[nx][ny] == piece:
                        count += 1
                    else:
                        break
            
            if count >= 5:
                return True
                
        return False

    def reset_game(self):
        self.board = [[' ' for _ in range(15)] for _ in range(15)]
        self.current_turn = PlayerRole.BLACK
        self.game_started = False
        self.move_history = []
        self.chat_history = []
        self.game_id = None
        self.broadcast({"type": "board", "board": self.board}, include_spectators=True)

if __name__ == "__main__":
    server = GomokuServer()
    server.start()