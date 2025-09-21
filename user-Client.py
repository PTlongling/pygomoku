import socket
import threading
import json
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
import time

class GomokuUserClient:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("五子棋用户端")
        self.root.geometry("700x800")
        
        self.frame_connect = tk.Frame(self.root)
        self.frame_connect.pack(pady=10)
        
        tk.Label(self.frame_connect, text="服务器地址:").grid(row=0, column=0)
        self.entry_host = tk.Entry(self.frame_connect, width=15)
        self.entry_host.insert(0, "localhost")
        self.entry_host.grid(row=0, column=1)
        
        tk.Label(self.frame_connect, text="端口:").grid(row=0, column=2)
        self.entry_port = tk.Entry(self.frame_connect, width=8)
        self.entry_port.insert(0, "8888")
        self.entry_port.grid(row=0, column=3)
        
        self.btn_connect = tk.Button(self.frame_connect, text="连接", command=self.connect_server)
        self.btn_connect.grid(row=0, column=4, padx=5)
        
        self.user_listbox = tk.Listbox(self.root, width=20, height=10)
        self.user_listbox.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        tk.Label(self.root, text="在线用户").pack(side=tk.RIGHT)
        
        self.chat_area = scrolledtext.ScrolledText(self.root, height=10, state='disabled')
        self.chat_area.pack(pady=5, padx=10, fill=tk.BOTH)
        
        self.frame_chat = tk.Frame(self.root)
        self.frame_chat.pack(pady=5, fill=tk.X)
        
        self.entry_chat = tk.Entry(self.frame_chat)
        self.entry_chat.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.entry_chat.bind("<Return>", self.send_chat)
        
        self.btn_send = tk.Button(self.frame_chat, text="发送", command=self.send_chat)
        self.btn_send.pack(side=tk.RIGHT, padx=5)
        
        self.canvas = tk.Canvas(self.root, width=450, height=450, bg="#E8C87E")
        self.canvas.pack(pady=10)
        
        self.control_frame = tk.Frame(self.root)
        self.control_frame.pack(pady=5)
        
        self.btn_replay = tk.Button(self.control_frame, text="查看回放", command=self.show_replay)
        self.btn_replay.pack(side=tk.LEFT, padx=5)
        
        self.btn_refresh = tk.Button(self.control_frame, text="刷新用户", command=self.refresh_user_list)
        self.btn_refresh.pack(side=tk.LEFT, padx=5)
        
        self.status = tk.Label(self.root, text="未连接", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.socket = None
        self.username = None
        self.role = None
        self.board = [[' ' for _ in range(15)] for _ in range(15)]
        self.cell_size = 30
        self.margin = 20
        self.users = {}
        self.move_history = []
        self.replay_mode = False
        self.replay_index = 0
        
        self.draw_board()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def draw_board(self):
        self.canvas.delete("all")
        for i in range(15):
            self.canvas.create_line(
                self.margin, 
                self.margin + i * self.cell_size,
                self.margin + 14 * self.cell_size,
                self.margin + i * self.cell_size
            )
            self.canvas.create_line(
                self.margin + i * self.cell_size, 
                self.margin,
                self.margin + i * self.cell_size,
                self.margin + 14 * self.cell_size
            )
        
        for i in range(15):
            for j in range(15):
                if self.board[i][j] != ' ':
                    color = "black" if self.board[i][j] == 'B' else "white"
                    self.canvas.create_oval(
                        self.margin + j * self.cell_size - 13,
                        self.margin + i * self.cell_size - 13,
                        self.margin + j * self.cell_size + 13,
                        self.margin + i * self.cell_size + 13,
                        fill=color, outline="black"
                    )
        
        self.canvas.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        if not self.socket or self.role == "SPECTATOR" or self.replay_mode:
            return
            
        x = event.x - self.margin
        y = event.y - self.margin
        
        if x < 0 or y < 0:
            return
            
        col = round(x / self.cell_size)
        row = round(y / self.cell_size)
        
        if 0 <= row < 15 and 0 <= col < 15:
            if self.board[row][col] == ' ':
                move_msg = {"type": "move", "x": row, "y": col}
                self.socket.send(json.dumps(move_msg).encode())
    
    def connect_server(self):
        try:
            host = self.entry_host.get()
            port = int(self.entry_port.get())
            
            self.username = simpledialog.askstring("用户名", "请输入用户名:", parent=self.root)
            if not self.username:
                return
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            
            login_msg = {"type": "login", "username": self.username, "is_admin": False}
            self.socket.send(json.dumps(login_msg).encode())
            
            self.btn_connect.config(state=tk.DISABLED)
            self.status.config(text="已连接，等待分配角色...")
            
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
        except Exception as e:
            messagebox.showerror("连接错误", f"无法连接到服务器: {e}")
    
    def receive_messages(self):
        buffer = ""
        while True:
            try:
                data = self.socket.recv(1024).decode()
                if not data:
                    break
                    
                buffer += data
                while buffer:
                    try:
                        message, idx = self.parse_json(buffer)
                        buffer = buffer[idx:]
                        self.process_message(message)
                        
                    except json.JSONDecodeError:
                        break
                    except ValueError:
                        buffer = ""
                        break
                
            except Exception as e:
                print(f"接收错误: {e}")
                break
    
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
    
    def process_message(self, message):
        if message["type"] == "role":
            self.role = message["role"]
            self.status.config(text=f"已连接 - 用户名: {self.username} - 角色: {self.role}")
            
        elif message["type"] == "game_start":
            self.add_chat("系统", message["message"])
            
        elif message["type"] == "move_made":
            x, y = message["x"], message["y"]
            self.board[x][y] = message["piece"]
            self.draw_board()
            self.add_chat("系统", f"{message['username']} 在 ({x}, {y}) 落子")
            
        elif message["type"] == "turn":
            turn = message["turn"]
            self.status.config(text=f"已连接 - 用户名: {self.username} - 角色: {self.role} - 当前回合: {turn}")
            
        elif message["type"] == "game_over":
            self.add_chat("系统", message["message"])
            self.show_victory(message["winner_name"], message["winner"])
            
        elif message["type"] == "game_force_end":
            self.add_chat("系统", f"⚠️ {message['message']} ⚠️")
            messagebox.showinfo("游戏结束", message["message"])
            self.reset_game()
            
        elif message["type"] == "board":
            self.board = message["board"]
            self.draw_board()
            
        elif message["type"] == "chat":
            if message["audience"] == "all" or (
                message["audience"] == "spectators" and self.role == "SPECTATOR"):
                self.add_chat(f"{message['username']}({message['role']})", message["message"])
            
        elif message["type"] == "broadcast":
            self.add_chat(f"📢 {message['from']}广播", f"📢 {message['message']} 📢")
            
        elif message["type"] == "error":
            self.add_chat("系统", message["message"])
            
        elif message["type"] == "user_joined":
            self.add_chat("系统", f"{message['username']} 以 {message['role']} 身份加入游戏")
            self.users[message["username"]] = {
                "role": message["role"],
                "address": message.get("address", "未知")
            }
            self.update_user_list()
            
        elif message["type"] == "user_left":
            self.add_chat("系统", f"{message['username']} 离开了游戏")
            if message["username"] in self.users:
                del self.users[message["username"]]
            self.update_user_list()
            
        elif message["type"] == "move_history":
            self.move_history = message["history"]
            
        elif message["type"] == "chat_history":
            for chat in message["history"]:
                if chat["audience"] == "all" or (
                    chat["audience"] == "spectators" and self.role == "SPECTATOR"):
                    self.add_chat(f"{chat['username']}({chat['role']})", chat["message"])
            
        elif message["type"] == "user_list":
            self.users = {}
            for user in message["users"]:
                self.users[user["username"]] = {
                    "role": user["role"],
                    "address": user["address"],
                    "is_admin": user["is_admin"]
                }
            self.update_user_list()
            
        elif message["type"] == "banned":
            messagebox.showerror("连接被拒绝", message["message"])
            self.on_closing()
            
        elif message["type"] == "kicked":
            messagebox.showwarning("被踢出", message["message"])
            self.on_closing()
            
        elif message["type"] == "cheat_detected":
            self.add_chat("系统", f"⚠️ 检测到作弊行为: {message['cheater']} - 原因: {message['reason']}")
            self.add_chat("系统", f"⚠️ {message['winner']} 获胜!")
            
        elif message["type"] == "cheating":
            messagebox.showerror("作弊检测", message["message"])
            self.on_closing()
    
    def send_chat(self, event=None):
        if not self.socket:
            return
            
        message = self.entry_chat.get().strip()
        if message:
            chat_msg = {"type": "chat", "message": message}
            self.socket.send(json.dumps(chat_msg).encode())
            self.entry_chat.delete(0, tk.END)
    
    def add_chat(self, sender, message):
        self.chat_area.config(state='normal')
        if sender:
            self.chat_area.insert(tk.END, f"{sender}: {message}\n")
        else:
            self.chat_area.insert(tk.END, f"{message}\n")
        self.chat_area.config(state='disabled')
        self.chat_area.see(tk.END)
    
    def update_user_list(self):
        self.user_listbox.delete(0, tk.END)
        for username, info in self.users.items():
            display_text = f"{username} ({info['role']})"
            if info.get("is_admin", False):
                display_text += " [管理员]"
            self.user_listbox.insert(tk.END, display_text)
    
    def refresh_user_list(self):
        if self.socket:
            self.update_user_list()
    
    def show_victory(self, winner_name, winner_role):
        victory_window = tk.Toplevel(self.root)
        victory_window.title("游戏结束")
        victory_window.geometry("300x200")
        
        tk.Label(victory_window, text=f"{winner_role}({winner_name}) 获胜!", 
                font=("Arial", 16)).pack(pady=20)
        
        tk.Button(victory_window, text="确定", command=victory_window.destroy).pack(pady=10)
        tk.Button(victory_window, text="查看回放", command=lambda: [victory_window.destroy(), self.show_replay()]).pack(pady=10)
    
    def reset_game(self):
        self.board = [[' ' for _ in range(15)] for _ in range(15)]
        self.draw_board()
    
    def show_replay(self):
        if not self.move_history:
            messagebox.showinfo("回放", "暂无历史记录")
            return
            
        replay_window = tk.Toplevel(self.root)
        replay_window.title("对局回放")
        replay_window.geometry("500x600")
        
        replay_canvas = tk.Canvas(replay_window, width=450, height=450, bg="#E8C87E")
        replay_canvas.pack(pady=10)
        
        for i in range(15):
            replay_canvas.create_line(
                self.margin, 
                self.margin + i * self.cell_size,
                self.margin + 14 * self.cell_size,
                self.margin + i * self.cell_size
            )
            replay_canvas.create_line(
                self.margin + i * self.cell_size, 
                self.margin,
                self.margin + i * self.cell_size,
                self.margin + 14 * self.cell_size
            )
        
        control_frame = tk.Frame(replay_window)
        control_frame.pack(pady=10)
        
        tk.Button(control_frame, text="第一步", command=lambda: self.set_replay_step(0, replay_canvas)).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="上一步", command=lambda: self.set_replay_step(self.replay_index-1, replay_canvas)).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="下一步", command=lambda: self.set_replay_step(self.replay_index+1, replay_canvas)).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="最后一步", command=lambda: self.set_replay_step(len(self.move_history)-1, replay_canvas)).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="自动播放", command=lambda: self.auto_play(replay_canvas, replay_window)).pack(side=tk.LEFT, padx=5)
        
        info_label = tk.Label(replay_window, text="")
        info_label.pack(pady=5)
        
        self.replay_mode = True
        self.replay_index = 0
        self.update_replay_display(replay_canvas, info_label)
        
        def on_close():
            self.replay_mode = False
            replay_window.destroy()
        
        replay_window.protocol("WM_DELETE_WINDOW", on_close)
    
    def set_replay_step(self, step, canvas):
        if step < 0:
            step = 0
        elif step >= len(self.move_history):
            step = len(self.move_history) - 1
            
        self.replay_index = step
        self.update_replay_display(canvas)
    
    def update_replay_display(self, canvas, info_label=None):
        canvas.delete("pieces")
        
        for i in range(self.replay_index + 1):
            move = self.move_history[i]
            color = "black" if move["piece"] == 'B' else "white"
            canvas.create_oval(
                self.margin + move["y"] * self.cell_size - 13,
                self.margin + move["x"] * self.cell_size - 13,
                self.margin + move["y"] * self.cell_size + 13,
                self.margin + move["x"] * self.cell_size + 13,
                fill=color, outline="black", tags="pieces"
            )
        
        if info_label and self.replay_index < len(self.move_history):
            move = self.move_history[self.replay_index]
            info_label.config(text=f"步数: {self.replay_index+1}/{len(self.move_history)} - {move['username']} 落子于 ({move['x']}, {move['y']})")
    
    def auto_play(self, canvas, window):
        def play():
            for i in range(len(self.move_history)):
                if not self.replay_mode:
                    return
                self.replay_index = i
                self.update_replay_display(canvas)
                window.update()
                time.sleep(1)
        
        threading.Thread(target=play, daemon=True).start()
    
    def on_closing(self):
        if self.socket:
            self.socket.close()
        self.root.destroy()

if __name__ == "__main__":
    client = GomokuUserClient()