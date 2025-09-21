import json
import tkinter as tk
from tkinter import filedialog, messagebox, Toplevel, Scrollbar, Text
import time
import os
from PIL import Image, ImageTk
import threading

class GomokuReplayViewer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("五子棋对局回放查看器")
        self.root.geometry("1000x800")
        self.menu_bar = tk.Menu(self.root)
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.file_menu.add_command(label="打开回放文件", command=self.open_replay_file)
        self.file_menu.add_command(label="打开聊天记录", command=self.open_chat_log)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="退出", command=self.root.quit)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)
        
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_menu.add_command(label="使用说明", command=self.show_help)
        self.menu_bar.add_cascade(label="帮助", menu=self.help_menu)
        self.root.config(menu=self.menu_bar)
        self.main_frame = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.left_frame = tk.Frame(self.main_frame)
        self.main_frame.add(self.left_frame, width=600)
        self.info_frame = tk.Frame(self.left_frame)
        self.info_frame.pack(pady=10, fill=tk.X)
        self.game_id_label = tk.Label(self.info_frame, text="对局ID: 未加载", font=("Arial", 10, "bold"))
        self.game_id_label.pack(side=tk.LEFT, padx=10)
        self.duration_label = tk.Label(self.info_frame, text="对局时长: 未加载")
        self.duration_label.pack(side=tk.LEFT, padx=10)
        self.winner_label = tk.Label(self.info_frame, text="获胜方: 未加载")
        self.winner_label.pack(side=tk.LEFT, padx=10)
        self.canvas_frame = tk.Frame(self.left_frame)
        self.canvas_frame.pack(pady=10)
        self.canvas = tk.Canvas(self.canvas_frame, width=450, height=450, bg="#E8C87E")
        self.canvas.pack()
        self.control_frame = tk.Frame(self.left_frame)
        self.control_frame.pack(pady=10)
        self.btn_first = tk.Button(self.control_frame, text="第一步", command=self.go_to_first)
        self.btn_first.pack(side=tk.LEFT, padx=5)
        self.btn_prev = tk.Button(self.control_frame, text="上一步", command=self.go_to_previous)
        self.btn_prev.pack(side=tk.LEFT, padx=5)
        self.btn_next = tk.Button(self.control_frame, text="下一步", command=self.go_to_next)
        self.btn_next.pack(side=tk.LEFT, padx=5)
        self.btn_last = tk.Button(self.control_frame, text="最后一步", command=self.go_to_last)
        self.btn_last.pack(side=tk.LEFT, padx=5)
        self.btn_play = tk.Button(self.control_frame, text="播放", command=self.toggle_play)
        self.btn_play.pack(side=tk.LEFT, padx=5)
        self.btn_help = tk.Button(self.control_frame, text="疑问", command=self.show_help)
        self.btn_help.pack(side=tk.LEFT, padx=5)
        self.progress_frame = tk.Frame(self.left_frame)
        self.progress_frame.pack(fill=tk.X, padx=20, pady=5)
        self.progress_label = tk.Label(self.progress_frame, text="步数: 0/0")
        self.progress_label.pack()
        self.progress_scale = tk.Scale(self.progress_frame, from_=0, to=0, orient=tk.HORIZONTAL, 
                                      command=self.on_progress_change, showvalue=False)
        self.progress_scale.pack(fill=tk.X)
        self.right_frame = tk.Frame(self.main_frame)
        self.main_frame.add(self.right_frame, width=400)
        self.detail_frame = tk.LabelFrame(self.right_frame, text="对局详情")
        self.detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.detail_text = Text(self.detail_frame, height=10, state=tk.DISABLED)
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self.chat_frame = tk.LabelFrame(self.right_frame, text="聊天记录")
        self.chat_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.chat_text = Text(self.chat_frame, height=15, state=tk.DISABLED)
        self.chat_text.pack(fill=tk.BOTH, expand=True)
        self.chat_control_frame = tk.Frame(self.right_frame)
        self.chat_control_frame.pack(fill=tk.X, padx=5, pady=2)
        self.chat_sync_var = tk.BooleanVar(value=True)
        self.chat_sync_check = tk.Checkbutton(self.chat_control_frame, text="同步聊天记录", 
                                              variable=self.chat_sync_var)
        self.chat_sync_check.pack(side=tk.LEFT)
        self.status_bar = tk.Label(self.root, text="就绪", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.replay_data = None
        self.chat_data = None
        self.current_step = 0
        self.total_steps = 0
        self.playing = False
        self.play_delay = 1.0  # 每秒一步
        self.cell_size = 30
        self.margin = 20
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
        star_points = [(3, 3), (3, 11), (7, 7), (11, 3), (11, 11)]
        for x, y in star_points:
            self.canvas.create_oval(
                self.margin + y * self.cell_size - 3,
                self.margin + x * self.cell_size - 3,
                self.margin + y * self.cell_size + 3,
                self.margin + x * self.cell_size + 3,
                fill="black"
            )
    def open_replay_file(self):
        file_path = filedialog.askopenfilename(
            title="选择回放文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            initialdir="replays" if os.path.exists("replays") else "."
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.replay_data = json.load(f)
            self.game_id_label.config(text=f"对局ID: {self.replay_data.get('game_id', '未知')}")
            start_time = self.replay_data.get('start_time', 0)
            end_time = self.replay_data.get('end_time', 0)
            duration = end_time - start_time
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            self.duration_label.config(text=f"对局时长: {minutes}分{seconds}秒")
            winner = self.replay_data.get('winner', '未知')
            self.winner_label.config(text=f"获胜方: {winner}")
            self.total_steps = len(self.replay_data.get('moves', []))
            self.current_step = 0
            self.progress_scale.config(to=self.total_steps)
            self.update_progress()
            self.update_detail_text()
            game_id = self.replay_data.get('game_id')
            if game_id:
                chat_path = os.path.join("chat_logs", f"{game_id}.json")
                if os.path.exists(chat_path):
                    self.load_chat_log(chat_path)
            self.draw_current_step()
            
            self.status_bar.config(text=f"已加载回放文件: {os.path.basename(file_path)}")
            
        except Exception as e:
            messagebox.showerror("错误", f"无法加载回放文件: {e}")
            self.status_bar.config(text="加载回放文件失败")
    
    def open_chat_log(self):
        """打开聊天记录文件"""
        file_path = filedialog.askopenfilename(
            title="选择聊天记录文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            initialdir="chat_logs" if os.path.exists("chat_logs") else "."
        )
        
        if not file_path:
            return
        
        self.load_chat_log(file_path)
    
    def load_chat_log(self, file_path):
        """加载聊天记录文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.chat_data = json.load(f)
            self.update_chat_display()
            
            self.status_bar.config(text=f"已加载聊天记录: {os.path.basename(file_path)}")
            
        except Exception as e:
            messagebox.showerror("错误", f"无法加载聊天记录文件: {e}")
            self.status_bar.config(text="加载聊天记录失败")
    
    def draw_current_step(self):
        """绘制当前步数的棋盘状态"""
        self.draw_board()
        for i in range(self.current_step):
            move = self.replay_data['moves'][i]
            color = "black" if move["piece"] == 'B' else "white"
            self.canvas.create_oval(
                self.margin + move["y"] * self.cell_size - 13,
                self.margin + move["x"] * self.cell_size - 13,
                self.margin + move["y"] * self.cell_size + 13,
                self.margin + move["x"] * self.cell_size + 13,
                fill=color, outline="black"
            )
        if self.current_step > 0:
            move = self.replay_data['moves'][self.current_step - 1]
            self.canvas.create_oval(
                self.margin + move["y"] * self.cell_size - 16,
                self.margin + move["x"] * self.cell_size - 16,
                self.margin + move["y"] * self.cell_size + 16,
                self.margin + move["x"] * self.cell_size + 16,
                outline="red", width=2
            )
    
    def update_progress(self):
        """更新进度显示"""
        self.progress_label.config(text=f"步数: {self.current_step}/{self.total_steps}")
        self.progress_scale.set(self.current_step)
    
    def update_detail_text(self):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete(1.0, tk.END)
        
        if self.replay_data:
            self.detail_text.insert(tk.END, f"对局ID: {self.replay_data.get('game_id', '未知')}\n")
            self.detail_text.insert(tk.END, f"棋盘大小: {self.replay_data.get('board_size', 15)}x{self.replay_data.get('board_size', 15)}\n")
            
            start_time = self.replay_data.get('start_time', 0)
            end_time = self.replay_data.get('end_time', 0)
            if start_time and end_time:
                start_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
                end_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))
                duration = end_time - start_time
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                self.detail_text.insert(tk.END, f"开始时间: {start_str}\n")
                self.detail_text.insert(tk.END, f"结束时间: {end_str}\n")
                self.detail_text.insert(tk.END, f"对局时长: {minutes}分{seconds}秒\n")
            
            self.detail_text.insert(tk.END, f"获胜方: {self.replay_data.get('winner', '未知')}\n\n")
            if self.current_step > 0:
                move = self.replay_data['moves'][self.current_step - 1]
                self.detail_text.insert(tk.END, f"当前步数: {self.current_step}\n")
                self.detail_text.insert(tk.END, f"玩家: {move['username']}\n")
                self.detail_text.insert(tk.END, f"棋子: {'黑棋' if move['piece'] == 'B' else '白棋'}\n")
                self.detail_text.insert(tk.END, f"位置: ({move['x']}, {move['y']})\n")
                
                move_time = move.get('timestamp', 0)
                if move_time:
                    time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(move_time))
                    self.detail_text.insert(tk.END, f"时间: {time_str}\n")
        
        self.detail_text.config(state=tk.DISABLED)
    
    def update_chat_display(self):
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete(1.0, tk.END)
        
        if self.chat_data:
            chats = self.chat_data.get('chats', [])
            for chat in chats:
                username = chat.get('username', '未知用户')
                role = chat.get('role', '未知身份')
                message = chat.get('message', '')
                timestamp = chat.get('timestamp', 0)
                
                if timestamp:
                    time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
                    self.chat_text.insert(tk.END, f"[{time_str}] {username}({role}): {message}\n")
                else:
                    self.chat_text.insert(tk.END, f"{username}({role}): {message}\n")
        
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)
    
    def update_chat_by_time(self, current_time):
        if not self.chat_data or not self.chat_sync_var.get():
            return
        
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete(1.0, tk.END)
        
        chats = self.chat_data.get('chats', [])
        for chat in chats:
            chat_time = chat.get('timestamp', 0)
            if chat_time <= current_time:
                username = chat.get('username', '未知用户')
                role = chat.get('role', '未知身份')
                message = chat.get('message', '')
                
                if chat_time:
                    time_str = time.strftime("%H:%M:%S", time.localtime(chat_time))
                    self.chat_text.insert(tk.END, f"[{time_str}] {username}({role}): {message}\n")
                else:
                    self.chat_text.insert(tk.END, f"{username}({role}): {message}\n")
        
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)
    
    def go_to_first(self):
        if self.replay_data:
            self.current_step = 0
            self.draw_current_step()
            self.update_progress()
            self.update_detail_text()
            if self.replay_data and self.current_step > 0:
                move = self.replay_data['moves'][self.current_step - 1]
                move_time = move.get('timestamp', 0)
                self.update_chat_by_time(move_time)
    
    def go_to_previous(self):
        """上一步"""
        if self.replay_data and self.current_step > 0:
            self.current_step -= 1
            self.draw_current_step()
            self.update_progress()
            self.update_detail_text()
            if self.current_step > 0:
                move = self.replay_data['moves'][self.current_step - 1]
                move_time = move.get('timestamp', 0)
                self.update_chat_by_time(move_time)
    
    def go_to_next(self):
        """下一步"""
        if self.replay_data and self.current_step < self.total_steps:
            self.current_step += 1
            self.draw_current_step()
            self.update_progress()
            self.update_detail_text()
            if self.current_step > 0:
                move = self.replay_data['moves'][self.current_step - 1]
                move_time = move.get('timestamp', 0)
                self.update_chat_by_time(move_time)
    
    def go_to_last(self):
        """跳到最后一步"""
        if self.replay_data:
            self.current_step = self.total_steps
            self.draw_current_step()
            self.update_progress()
            self.update_detail_text()
            if self.current_step > 0:
                move = self.replay_data['moves'][self.current_step - 1]
                move_time = move.get('timestamp', 0)
                self.update_chat_by_time(move_time)
    
    def on_progress_change(self, value):
        """进度条变化事件"""
        if self.replay_data:
            step = int(float(value))
            if step != self.current_step:
                self.current_step = step
                self.draw_current_step()
                self.update_progress()
                self.update_detail_text()
                if self.current_step > 0:
                    move = self.replay_data['moves'][self.current_step - 1]
                    move_time = move.get('timestamp', 0)
                    self.update_chat_by_time(move_time)
    
    def toggle_play(self):
        """切换播放状态"""
        if not self.replay_data:
            return
        
        self.playing = not self.playing
        if self.playing:
            self.btn_play.config(text="暂停")
            self.play_animation()
        else:
            self.btn_play.config(text="播放")
    
    def play_animation(self):
        """播放动画"""
        if not self.playing or not self.replay_data:
            return
        
        if self.current_step < self.total_steps:
            self.current_step += 1
            self.draw_current_step()
            self.update_progress()
            self.update_detail_text()
            if self.current_step > 0:
                move = self.replay_data['moves'][self.current_step - 1]
                move_time = move.get('timestamp', 0)
                self.update_chat_by_time(move_time)
            
            self.root.after(int(self.play_delay * 1000), self.play_animation)
        else:
            self.playing = False
            self.btn_play.config(text="播放")
    
    def show_help(self):
        """显示使用说明"""
        help_window = Toplevel(self.root)
        help_window.title("使用说明")
        help_window.geometry("600x400")
        
        help_text = Text(help_window, wrap=tk.WORD, padx=10, pady=10)
        help_text.pack(fill=tk.BOTH, expand=True)
        
        help_content = """
五子棋对局回放查看器使用说明

1. 打开回放文件
   - 点击菜单栏的"文件" -> "打开回放文件"
   - 选择要查看的回放JSON文件
   - 程序会自动尝试加载对应的聊天记录

2. 打开聊天记录
   - 如果需要单独加载聊天记录，点击"文件" -> "打开聊天记录"
   - 选择对应的聊天记录JSON文件

3. 控制播放
   - 使用"第一步"、"上一步"、"下一步"、"最后一步"按钮控制播放进度
   - 使用进度条快速跳转到指定步数
   - 点击"播放"按钮自动播放整个对局

4. 聊天记录同步
   - 勾选"同步聊天记录"可以在播放对局时同步显示聊天内容
   - 取消勾选则显示所有聊天记录

5. 查看详细信息
   - 右侧面板显示对局详细信息和聊天记录
   - 对局信息包括步数、玩家、棋子类型、位置和时间
   - 聊天记录显示对局过程中的所有聊天内容

6. 获取回放文件
   - 回放文件需要向管理员申请获取
   - 回放文件保存在服务器的replays目录中
   - 聊天记录保存在服务器的chat_logs目录中

注意事项：
- 确保回放文件和聊天记录文件来自同一局游戏
- 回放文件格式为JSON，包含对局的每一步信息
- 聊天记录文件格式为JSON，包含对局过程中的所有聊天内容
- 如果遇到问题，请联系管理员获取帮助
"""
        
        help_text.insert(1.0, help_content)
        help_text.config(state=tk.DISABLED)
        
        close_button = tk.Button(help_window, text="关闭", command=help_window.destroy)
        close_button.pack(pady=10)
    
    def on_closing(self):
        """关闭窗口时的处理"""
        self.playing = False
        self.root.destroy()

if __name__ == "__main__":
    app = GomokuReplayViewer()
