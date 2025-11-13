import socket
import threading
import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import time
import sys


class MessengerClient:
    def __init__(self):
        self.socket = None
        self.username = None
        self.user_ip = self.get_local_ip()
        self.server_ip = None  # IP, который видит серверр
        self.private_chats = {}  # chat_display_name -> username
        self.group_chats = {}  # chat_display_name -> group_name
        self.chat_history = {}  # chat_id -> list of messages (локальное хранение)
        self.pending_messages = {}  # message_id -> message data
        self.group_creators = {}  # group_name -> creator
        self.user_ips = {}  # username -> IP mapping (локальные IP)
        self.user_server_ips = {}  # username -> серверные IP
        self.group_members = {}  # group_name -> list of members with IPs
        self.pending_member_requests = set()  # group_name для которых запрошены участники

        self.setup_gui()
        self.connect_to_server()

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def setup_gui(self):
        # Настройка цветовой схемы
        self.colors = {
            'primary': '#2c3e50',
            'secondary': '#34495e',
            'accent': '#3498db',
            'success': '#2ecc71',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#2c3e50',
            'text_light': '#ffffff',
            'text_dark': '#2c3e50'
        }

        self.root = tk.Tk()
        self.root.title("Messenger")
        self.root.geometry("800x650")
        self.root.configure(bg=self.colors['light'])
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

        # Стили для ttk
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Настройка стилей
        self.style.configure('TFrame', background=self.colors['light'])
        self.style.configure('TLabel', background=self.colors['light'], foreground=self.colors['dark'])
        self.style.configure('TButton', background=self.colors['accent'], foreground=self.colors['text_light'])
        self.style.configure('Primary.TButton', background=self.colors['primary'], foreground=self.colors['text_light'])
        self.style.configure('Secondary.TButton', background=self.colors['secondary'], foreground=self.colors['text_light'])
        self.style.configure('TEntry', fieldbackground=self.colors['light'])
        self.style.configure('TCanvas', background=self.colors['light'])
        self.style.configure('TScrollbar', background=self.colors['secondary'])

        # Регистрация
        self.login_frame = ttk.Frame(self.root, style='TFrame')
        self.login_frame.pack(pady=50)

        ttk.Label(self.login_frame, text="Введите ваше имя:", font=('Arial', 12, 'bold')).pack(pady=10)
        self.username_entry = ttk.Entry(self.login_frame, width=30, font=('Arial', 11))
        self.username_entry.pack(pady=10)
        self.username_entry.bind('<Return>', lambda e: self.register_user())

        ttk.Button(self.login_frame, text="Войти", command=self.register_user, style='Primary.TButton').pack(pady=10)

        # Основной интерфейс
        self.main_frame = ttk.Frame(self.root, style='TFrame')

        # Верхняя панель
        top_frame = ttk.Frame(self.main_frame, style='TFrame')
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        self.user_label = ttk.Label(top_frame, text="", font=('Arial', 10, 'bold'))
        self.user_label.pack(side=tk.LEFT)

        # Кнопка добавления чатов
        self.add_button = ttk.Button(top_frame, text="+ Добавить чат", command=self.show_add_menu, style='Secondary.TButton')
        self.add_button.pack(side=tk.RIGHT, padx=(5, 0))

        # Кнопка выхода
        self.exit_button = ttk.Button(top_frame, text="Выйти", command=self.exit_app, style='TButton')
        self.exit_button.pack(side=tk.RIGHT)

        # Основной контейнер с разделением на чаты и сообщения
        main_container = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Левая панель - список чатов
        left_frame = ttk.Frame(main_container, style='TFrame')
        main_container.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Чаты:", font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        # Поиск чатов
        search_frame = ttk.Frame(left_frame, style='TFrame')
        search_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind('<KeyRelease>', self.filter_chats)

        # Список чатов с прокруткой
        chat_list_frame = ttk.Frame(left_frame, style='TFrame')
        chat_list_frame.pack(fill=tk.BOTH, expand=True)

        # Создаем Canvas и Scrollbar для кастомного списка чатов
        self.chat_canvas = tk.Canvas(chat_list_frame, bg=self.colors['light'], highlightthickness=0)
        scrollbar_chats = ttk.Scrollbar(chat_list_frame, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        self.chat_scrollable_frame = ttk.Frame(self.chat_canvas, style='TFrame')

        self.chat_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(
                scrollregion=self.chat_canvas.bbox("all")
            )
        )

        self.chat_canvas.create_window((0, 0), window=self.chat_scrollable_frame, anchor="nw")
        self.chat_canvas.configure(yscrollcommand=scrollbar_chats.set)

        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_chats.pack(side=tk.RIGHT, fill=tk.Y)

        # Правая панель - сообщения
        right_frame = ttk.Frame(main_container, style='TFrame')
        main_container.add(right_frame, weight=2)

        # Заголовок текущего чата
        self.chat_title = ttk.Label(right_frame, text="Выберите чат", font=('Arial', 12, 'bold'))
        self.chat_title.pack(anchor=tk.W, pady=(0, 10))

        # Область сообщений с прокруткой
        messages_frame = ttk.Frame(right_frame, style='TFrame')
        messages_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_area = tk.Text(messages_frame, state=tk.DISABLED, font=('Arial', 10), 
                                bg=self.colors['light'], fg=self.colors['dark'],
                                relief='flat', padx=10, pady=10)
        scrollbar_messages = ttk.Scrollbar(messages_frame, orient=tk.VERTICAL, command=self.chat_area.yview)
        self.chat_area.config(yscrollcommand=scrollbar_messages.set)

        self.chat_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_messages.pack(side=tk.RIGHT, fill=tk.Y)

        # Панель ввода сообщения
        input_frame = ttk.Frame(right_frame, style='TFrame')
        input_frame.pack(fill=tk.X, pady=(10, 0))

        self.message_entry = ttk.Entry(input_frame, font=('Arial', 10))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_entry.bind('<Return>', lambda e: self.send_message())
        self.message_entry.config(state='disabled')

        self.send_button = ttk.Button(input_frame, text="Отправить", command=self.send_message, style='Primary.TButton')
        self.send_button.pack(side=tk.RIGHT)
        self.send_button.config(state='disabled')

        self.current_chat = None
        self.current_chat_type = None
        self.current_chat_id = None

        # Статусная строка
        self.status_var = tk.StringVar()
        self.status_var.set("Не подключено")
        status_bar = ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN, style='TLabel')
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)

        # Словарь для хранения виджетов чатов
        self.chat_widgets = {}

    def create_chat_widget(self, chat_name, chat_type, chat_data, creator=None):
        """Создание виджета для чата с меню"""
        chat_frame = ttk.Frame(self.chat_scrollable_frame, style='TFrame')
        chat_frame.pack(fill=tk.X, padx=5, pady=2)

        # Основная кнопка чата
        chat_button = ttk.Button(
            chat_frame,
            text=chat_name,
            command=lambda: self.select_chat(chat_name, chat_type, chat_data),
            width=30,
            style='TButton'
        )
        chat_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Кнопка меню (три точки)
        menu_button = ttk.Button(chat_frame, text="⋯", width=2,
                                 command=lambda: self.show_chat_menu(chat_name, chat_type, chat_data, menu_button,
                                                                     creator))
        menu_button.pack(side=tk.RIGHT)

        self.chat_widgets[chat_name] = {
            'frame': chat_frame,
            'button': chat_button,
            'menu_button': menu_button,
            'type': chat_type,
            'data': chat_data
        }

        # Для личных чатов сразу запрашиваем историю
        if chat_type == 'private':
            self.request_chat_history('private', chat_data)

    def show_chat_menu(self, chat_name, chat_type, chat_data, menu_button, creator=None):
        """Показать меню для чата/группы"""
        menu = tk.Menu(self.root, tearoff=0, bg=self.colors['light'], fg=self.colors['dark'])

        if chat_type == 'group':
            # Для групп проверяем, является ли пользователь создателем
            is_creator = (self.username == creator)

            if is_creator:
                menu.add_command(label="Переименовать",
                                 command=lambda: self.rename_group(chat_name, chat_data))
                menu.add_command(label="Удалить группу",
                                 command=lambda: self.delete_group(chat_name, chat_data))
            else:
                menu.add_command(label="Покинуть группу",
                                 command=lambda: self.leave_group(chat_name, chat_data))
            
            # Добавляем пункт для просмотра участников
            menu.add_separator()
            menu.add_command(label="Участники",
                           command=lambda: self.show_group_members(chat_data))
        else:
            menu.add_command(label="Удалить чат",
                             command=lambda: self.delete_private_chat(chat_name, chat_data))

        # Показываем меню рядом с кнопкой
        menu.tk_popup(menu_button.winfo_rootx(),
                      menu_button.winfo_rooty() + menu_button.winfo_height())

    def show_group_members(self, group_name):
        """Показать окно со списком участников группы"""
        members_window = tk.Toplevel(self.root)
        members_window.title(f"Участники группы: {group_name}")
        members_window.geometry("500x500")
        members_window.configure(bg=self.colors['light'])
        members_window.resizable(False, False)

        # Центрируем окно
        members_window.transient(self.root)
        members_window.grab_set()

        # Заголовок
        title_label = ttk.Label(members_window, text=f"Участники группы '{group_name}':", 
                               font=('Arial', 12, 'bold'))
        title_label.pack(pady=10)

        # Прокручиваемый список участников
        members_frame = ttk.Frame(members_window, style='TFrame')
        members_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Canvas для прокрутки
        canvas = tk.Canvas(members_frame, bg=self.colors['light'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(members_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='TFrame')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Запрашиваем список участников у сервера
        if group_name not in self.pending_member_requests:
            self.pending_member_requests.add(group_name)
            self.request_group_members(group_name)

        # Функция для обновления списка участников
        def update_members_display():
            # Очищаем текущий список
            for widget in scrollable_frame.winfo_children():
                widget.destroy()

            # Отображаем участников
            if group_name in self.group_members:
                members = self.group_members[group_name]
                for member_info in members:
                    member_frame = ttk.Frame(scrollable_frame, style='TFrame')
                    member_frame.pack(fill=tk.X, padx=5, pady=2)

                    username = member_info['username']
                    user_local_ip = member_info['local_ip']
                    user_server_ip = member_info['server_ip']
                    
                    # Цвет создателя группы
                    is_creator = username == self.group_creators.get(group_name)
                    creator_color = self.colors['warning'] if is_creator else self.colors['dark']
                    
                    # Информация о пользователе
                    user_info = f"{username} (локальный: {user_local_ip}, серверный: {user_server_ip})"
                    if is_creator:
                        user_info += " - создатель"
                    
                    # Создаем кликабельную метку для участника
                    member_label = ttk.Label(
                        member_frame, 
                        text=user_info, 
                        font=('Arial', 10),
                        cursor="hand2"
                    )
                    member_label.configure(foreground=creator_color)
                    member_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

                    # Делаем метку кликабельной
                    member_label.bind('<Button-1>', 
                                    lambda e, u=username: self.create_private_chat_from_member(u))

                    if username == self.username:
                        you_label = ttk.Label(member_frame, text=" (Вы)", foreground=self.colors['accent'])
                        you_label.pack(side=tk.LEFT)
            else:
                # Если участники еще не загружены, показываем сообщение
                loading_label = ttk.Label(scrollable_frame, text="Загрузка участников...")
                loading_label.pack(pady=10)

                # Планируем повторную проверку через 0.5 секунды
                members_window.after(500, update_members_display)

        # Первоначальное отображение
        update_members_display()

        # Функция для обновления при получении данных
        def on_members_update():
            if group_name in self.group_members:
                update_members_display()
            else:
                members_window.after(100, on_members_update)

        # Запускаем отслеживание обновлений
        on_members_update()

        # Кнопка закрытия
        close_button = ttk.Button(members_window, text="Закрыть", 
                                 command=members_window.destroy, style='Primary.TButton')
        close_button.pack(pady=10)

    def create_private_chat_from_member(self, username):
        """Создание личного чата с участником группы"""
        if username == self.username:
            messagebox.showinfo("Информация", "Нельзя создать чат с самим собой")
            return

        chat_name = f"Личный: {username}"
        if chat_name not in self.chat_widgets:
            self.create_chat_widget(chat_name, 'private', username)
            self.private_chats[chat_name] = username
            messagebox.showinfo("Успех", f"Создан чат с {username}")
        else:
            messagebox.showinfo("Информация", f"Чат с {username} уже существует")

    def request_group_members(self, group_name):
        """Запрос списка участников группы у сервера"""
        message = {
            'type': 'get_group_members',
            'group_name': group_name,
            'username': self.username
        }
        try:
            self.socket.send(json.dumps(message).encode('utf-8'))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось запросить список участников: {e}")

    def select_chat(self, chat_name, chat_type, chat_data):
        """Выбор чата"""
        self.current_chat = chat_name

        # Активируем поле ввода сообщения
        self.message_entry.config(state='normal')
        self.send_button.config(state='normal')

        if chat_type == 'private':
            self.current_chat_type = 'private'
            self.current_chat_id = chat_data
            user_local_ip = self.user_ips.get(chat_data, 'Неизвестно')
            user_server_ip = self.user_server_ips.get(chat_data, 'Неизвестно')
            self.chat_title.config(text=f"Личный чат с {chat_data} (локальный: {user_local_ip}, серверный: {user_server_ip})")
            # Для личных чатов используем локальную историю
            self.display_local_chat_history(chat_data)
        else:
            self.current_chat_type = 'group'
            self.current_chat_id = chat_data
            self.chat_title.config(text=f"Группа: {chat_data}")
            self.request_chat_history('group', chat_data)

    def display_local_chat_history(self, user_id):
        """Отображение локальной истории личного чата"""
        chat_key = f"private_{user_id}"
        history = self.chat_history.get(chat_key, [])

        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete(1.0, tk.END)

        if history:
            for msg in history:
                timestamp = datetime.fromisoformat(msg['timestamp']).strftime("%H:%M")
                sender = msg['from']
                local_ip = msg.get('local_ip', 'Неизвестно')
                server_ip = msg.get('server_ip', 'Неизвестно')

                # Для всех сообщений показываем оба IP
                ip_info = f"локальный: {local_ip}, серверный: {server_ip}"

                self.chat_area.insert(tk.END, f"[{timestamp}] {sender} ({ip_info}): {msg['text']}\n")
        else:
            self.chat_area.insert(tk.END, "Нет сообщений\n")

        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def rename_group(self, chat_name, group_name):
        """Переименование группы"""
        new_name = simpledialog.askstring("Переименовать группу",
                                          "Введите новое название группы:",
                                          initialvalue=group_name)
        if new_name and new_name != group_name:
            message = {
                'type': 'rename_group',
                'group_name': group_name,
                'new_name': new_name,
                'username': self.username
            }
            self.socket.send(json.dumps(message, ensure_ascii=False).encode('utf-8'))

    def delete_group(self, chat_name, group_name):
        """Удаление группы"""
        if messagebox.askyesno("Удалить группу",
                               f"Вы уверены, что хотите удалить группу '{group_name}'?"):
            message = {
                'type': 'delete_group',
                'group_name': group_name,
                'username': self.username
            }
            self.socket.send(json.dumps(message).encode('utf-8'))

    def leave_group(self, chat_name, group_name):
        """Покинуть группу"""
        if messagebox.askyesno("Покинуть группу",
                               f"Вы уверены, что хотите покинуть группу '{group_name}'?"):
            message = {
                'type': 'leave_group',
                'group_name': group_name,
                'username': self.username
            }
            self.socket.send(json.dumps(message).encode('utf-8'))

    def delete_private_chat(self, chat_name, username):
        """Удаление личного чата"""
        if messagebox.askyesno("Удалить чат",
                               f"Вы уверены, что хотите удалить чат с '{username}'?"):
            # Удаляем чат из интерфейса
            self.remove_chat_widget(chat_name)

            # Удаляем локальную историю
            chat_key = f"private_{username}"
            if chat_key in self.chat_history:
                del self.chat_history[chat_key]

            # Если этот чат был выбран, сбрасываем выбор
            if self.current_chat == chat_name:
                self.deselect_chat()

    def remove_chat_widget(self, chat_name):
        """Удаление виджета чата"""
        if chat_name in self.chat_widgets:
            self.chat_widgets[chat_name]['frame'].destroy()
            del self.chat_widgets[chat_name]

            # Также удаляем из внутренних словарей
            if chat_name in self.private_chats:
                del self.private_chats[chat_name]
            elif chat_name in self.group_chats:
                del self.group_chats[chat_name]
                if chat_name in self.group_creators:
                    del self.group_creators[chat_name]

    def filter_chats(self, event):
        """Фильтрация чатов по поисковому запросу"""
        search_text = self.search_entry.get().lower()

        # Показываем/скрываем чаты в зависимости от поискового запроса
        for chat_name, widget_info in self.chat_widgets.items():
            if search_text in chat_name.lower():
                widget_info['frame'].pack(fill=tk.X, padx=5, pady=2)
            else:
                widget_info['frame'].pack_forget()

    def connect_to_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect(('localhost', 5000))
            self.status_var.set("Подключено к серверу")

            # Запускаем поток для приема сообщений
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
        except Exception as e:
            self.status_var.set(f"Ошибка подключения: {e}")
            messagebox.showerror("Ошибка", f"Не удалось подключиться к серверу: {e}")

    def register_user(self):
        username = self.username_entry.get().strip()
        if username:
            self.username = username
            register_msg = {
                'type': 'register',
                'username': username,
                'local_ip': self.user_ip  # Отправляем локальный IP
            }
            try:
                self.socket.send(json.dumps(register_msg).encode('utf-8'))

                self.login_frame.pack_forget()
                self.main_frame.pack(fill=tk.BOTH, expand=True)

                # Получаем серверный IP после регистрации
                self.get_server_ip()

                self.root.title(f"Messenger - {username}")
                self.status_var.set(f"Зарегистрирован как {username}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось зарегистрироваться: {e}")

    def get_server_ip(self):
        """Получение серверного IP пользователя"""
        # В реальном приложении сервер должен отправлять IP пользователя
        # Для демонстрации используем локальный IP
        self.server_ip = self.user_ip  # В реальности это должен быть IP, который видит сервер
        self.user_label.config(text=f"{self.username} (локальный: {self.user_ip}, серверный: {self.server_ip})")

    def show_add_menu(self):
        menu = tk.Menu(self.root, tearoff=0, bg=self.colors['light'], fg=self.colors['dark'])
        menu.add_command(label="Личный чат", command=self.add_private_chat)
        menu.add_command(label="Создать группу", command=self.create_group)
        menu.add_command(label="Вступить в группу", command=self.join_group)

        menu.tk_popup(self.add_button.winfo_rootx(),
                      self.add_button.winfo_rooty() + self.add_button.winfo_height())

    def add_private_chat(self):
        username = simpledialog.askstring("Личный чат", "Введите имя пользователя:")
        if username:
            chat_name = f"Личный: {username}"
            if chat_name not in self.chat_widgets:
                self.create_chat_widget(chat_name, 'private', username)
                self.private_chats[chat_name] = username
                # История будет запрошена автоматически в create_chat_widget

    def create_group(self):
        group_name = simpledialog.askstring("Создать группу", "Введите название группы:")
        if group_name:
            create_msg = {
                'type': 'create_group',
                'group_name': group_name,
                'creator': self.username
            }
            self.socket.send(json.dumps(create_msg).encode('utf-8'))

    def join_group(self):
        group_name = simpledialog.askstring("Вступить в группу", "Введите название группы:")
        if group_name:
            join_msg = {
                'type': 'join_group',
                'group_name': group_name,
                'username': self.username
            }
            self.socket.send(json.dumps(join_msg).encode('utf-8'))

    def deselect_chat(self):
        """Сброс выбора чата"""
        self.current_chat = None
        self.current_chat_type = None
        self.current_chat_id = None

        # Деактивируем поле ввода
        self.message_entry.config(state='disabled')
        self.send_button.config(state='disabled')
        self.message_entry.delete(0, tk.END)

        # Очищаем область сообщений
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete(1.0, tk.END)
        self.chat_area.config(state=tk.DISABLED)

        # Сбрасываем заголовок
        self.chat_title.config(text="Выберите чат")

    def request_chat_history(self, chat_type, chat_id):
        """Запрос истории чата у сервера"""
        message = {
            'type': 'get_chat_history',
            'chat_type': chat_type,
            'chat_id': chat_id,
            'username': self.username
        }
        self.socket.send(json.dumps(message).encode('utf-8'))

    def display_chat_history(self, history):
        """Отображение истории чата (для групп)"""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete(1.0, tk.END)

        if history:
            for msg in history:
                timestamp = datetime.fromisoformat(msg['timestamp']).strftime("%H:%M")
                sender = msg['from']
                local_ip = msg.get('local_ip', 'Неизвестно')
                server_ip = msg.get('server_ip', 'Неизвестно')

                # Для всех сообщений показываем оба IP
                ip_info = f"локальный: {local_ip}, серверный: {server_ip}"

                self.chat_area.insert(tk.END, f"[{timestamp}] {sender} ({ip_info}): {msg['text']}\n")
        else:
            self.chat_area.insert(tk.END, "Нет сообщений\n")

        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def generate_message_id(self):
        """Генерация уникального ID для сообщения"""
        return f"{self.username}_{int(time.time() * 1000)}"

    def send_message(self):
        if not self.current_chat or not self.current_chat_type:
            messagebox.showwarning("Предупреждение", "Выберите чат для отправки сообщения")
            return

        message_text = self.message_entry.get().strip()
        if not message_text:
            return

        # Генерируем ID сообщения для отслеживания
        message_id = self.generate_message_id()

        if self.current_chat_type == 'private':
            # Личное сообщение
            target_user = self.private_chats[self.current_chat]
            message = {
                'type': 'private_message',
                'from': self.username,
                'to': target_user,
                'text': message_text,
                'message_id': message_id,
                'local_ip': self.user_ip,
                'server_ip': self.server_ip
            }

            # Сохраняем сообщение в локальной истории
            chat_key = f"private_{target_user}"
            if chat_key not in self.chat_history:
                self.chat_history[chat_key] = []

            msg_data = {
                'from': self.username,
                'local_ip': self.user_ip,
                'server_ip': self.server_ip,
                'text': message_text,
                'timestamp': datetime.now().isoformat()
            }
            self.chat_history[chat_key].append(msg_data)

            # Если чат открыт, сразу отображаем сообщение
            if (self.current_chat_type == 'private' and
                    self.current_chat_id == target_user):
                self.display_message(self.username, self.user_ip, self.server_ip, message_text)

        else:
            # Групповое сообщение
            if self.current_chat in self.group_chats:
                group_name = self.group_chats[self.current_chat]
                message = {
                    'type': 'group_message',
                    'from': self.username,
                    'group': group_name,
                    'text': message_text,
                    'message_id': message_id,
                    'local_ip': self.user_ip,
                    'server_ip': self.server_ip
                }
            else:
                messagebox.showerror("Ошибка", "Группа не найдена")
                return

        try:
            self.socket.send(json.dumps(message, ensure_ascii=False).encode('utf-8'))
            self.message_entry.delete(0, tk.END)

            # Сохраняем сообщение как ожидающее подтверждения
            self.pending_messages[message_id] = {
                'type': self.current_chat_type,
                'text': message_text,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось отправить сообщение: {e}")

    def display_message(self, sender, local_ip, server_ip, text, timestamp=None):
        """Отображение нового сообщения"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        time_str = datetime.fromisoformat(timestamp).strftime("%H:%M")

        # Для всех сообщений показываем оба IP
        ip_info = f"локальный: {local_ip}, серверный: {server_ip}"

        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"[{time_str}] {sender} ({ip_info}): {text}\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def receive_messages(self):
        while True:
            try:
                data = self.socket.recv(1024).decode('utf-8')
                if not data:
                    break

                message = json.loads(data)
                msg_type = message.get('type')

                if msg_type == 'private_message':
                    sender = message['from']
                    local_ip = message.get('local_ip', 'Неизвестно')
                    server_ip = message.get('server_ip', 'Неизвестно')
                    text = message['text']
                    timestamp = message.get('timestamp')

                    # Сохраняем IP отправителя
                    self.user_ips[sender] = local_ip
                    self.user_server_ips[sender] = server_ip

                    # Сохраняем сообщение в локальной истории
                    chat_key = f"private_{sender}"
                    if chat_key not in self.chat_history:
                        self.chat_history[chat_key] = []

                    msg_data = {
                        'from': sender,
                        'local_ip': local_ip,
                        'server_ip': server_ip,
                        'text': text,
                        'timestamp': timestamp
                    }
                    self.chat_history[chat_key].append(msg_data)

                    # Проверяем, есть ли уже чат с этим пользователем
                    chat_name = f"Личный: {sender}"
                    if chat_name not in self.private_chats:
                        # Автоматически создаем чат с новым пользователем
                        self.private_chats[chat_name] = sender
                        self.create_chat_widget(chat_name, 'private', sender)

                    # Проверяем, открыт ли сейчас этот личный чат
                    if (self.current_chat_type == 'private' and
                            self.current_chat_id == sender):
                        # Если чат открыт, сразу отображаем сообщение
                        self.display_message(sender, local_ip, server_ip, text, timestamp)
                    else:
                        # Уведомление о новом сообщении
                        self.status_var.set(f"Новое сообщение от {sender}")

                elif msg_type == 'group_message':
                    sender = message['from']
                    local_ip = message.get('local_ip', 'Неизвестно')
                    server_ip = message.get('server_ip', 'Неизвестно')
                    group_name = message['group']
                    text = message['text']
                    timestamp = message.get('timestamp')

                    # Сохраняем IP отправителя
                    self.user_ips[sender] = local_ip
                    self.user_server_ips[sender] = server_ip

                    # Проверяем, открыта ли сейчас эта группа
                    if (self.current_chat_type == 'group' and
                            self.current_chat_id == group_name):
                        self.display_message(sender, local_ip, server_ip, text, timestamp)
                    else:
                        # Уведомление о новом сообщении в группе
                        self.status_var.set(f"Новое сообщение в {group_name} от {sender}")

                elif msg_type == 'message_sent':
                    # Подтверждение отправки сообщения
                    message_id = message.get('message_id')
                    if message_id in self.pending_messages:
                        # Удаляем из ожидающих подтверждения
                        del self.pending_messages[message_id]

                elif msg_type == 'chats_update':
                    # Обновление списка чатов
                    self.update_chats_list(message)

                elif msg_type == 'chat_history':
                    # Получение истории чата от сервера
                    chat_type = message['chat_type']
                    chat_id = message['chat_id']
                    history = message['history']

                    if chat_type == 'private':
                        # Для личных чатов сохраняем историю локально
                        chat_key = f"private_{chat_id}"
                        self.chat_history[chat_key] = history

                        # Если чат открыт, обновляем отображение
                        if (self.current_chat_type == 'private' and
                                self.current_chat_id == chat_id):
                            self.display_local_chat_history(chat_id)
                    else:
                        # Для групп просто отображаем историю
                        if (self.current_chat_type == 'group' and
                                self.current_chat_id == chat_id):
                            self.display_chat_history(history)

                elif msg_type == 'group_created':
                    group_name = message['group_name']
                    chat_name = f"Группа: {group_name}"
                    if chat_name not in self.chat_widgets:
                        # Создатель - текущий пользователь
                        self.create_chat_widget(chat_name, 'group', group_name, self.username)
                        self.group_chats[chat_name] = group_name
                        self.group_creators[chat_name] = self.username

                elif msg_type == 'group_joined':
                    group_name = message['group_name']
                    chat_name = f"Группа: {group_name}"
                    if chat_name not in self.chat_widgets:
                        # При присоединении создатель неизвестен, будет обновлено в chats_update
                        self.create_chat_widget(chat_name, 'group', group_name)
                        self.group_chats[chat_name] = group_name

                elif msg_type == 'group_members':
                    # Получение списка участников группы
                    group_name = message['group_name']
                    members = message['members']
                    self.group_members[group_name] = members
                    
                    # Убираем группу из ожидающих запросов
                    if group_name in self.pending_member_requests:
                        self.pending_member_requests.remove(group_name)
                    
                    self.status_var.set(f"Получен список участников группы {group_name}")

                elif msg_type == 'server_ip_assigned':
                    # Получение серверного IP от сервера
                    self.server_ip = message['server_ip']
                    self.user_label.config(text=f"{self.username} (локальный: {self.user_ip}, серверный: {self.server_ip})")

            except Exception as e:
                self.status_var.set(f"Ошибка получения сообщения: {e}")
                break

    def update_chats_list(self, message):
        """Обновление списка чатов"""
        # Очищаем текущие чаты
        for widget in self.chat_widgets.values():
            widget['frame'].destroy()
        self.chat_widgets.clear()
        self.private_chats.clear()
        self.group_chats.clear()
        self.group_creators.clear()

        # Добавляем личные чаты с IP
        for chat in message.get('private_chats', []):
            chat_name = f"Личный: {chat['user']}"
            self.create_chat_widget(chat_name, 'private', chat['user'])
            self.private_chats[chat_name] = chat['user']
            # Сохраняем IP пользователя
            self.user_ips[chat['user']] = chat.get('local_ip', 'Неизвестно')
            self.user_server_ips[chat['user']] = chat.get('server_ip', 'Неизвестно')

        # Добавляем групповые чаты
        for chat in message.get('group_chats', []):
            chat_name = f"Группа: {chat['group_name']}"
            creator = chat.get('creator', 'Неизвестно')
            self.create_chat_widget(chat_name, 'group', chat['group_name'], creator)
            self.group_chats[chat_name] = chat['group_name']
            self.group_creators[chat_name] = creator

        # Если текущий чат был удален, сбрасываем выбор
        if (self.current_chat and
                self.current_chat not in self.private_chats and
                self.current_chat not in self.group_chats):
            self.deselect_chat()
        # Если текущий чат все еще существует, обновляем заголовок
        elif self.current_chat_type == 'private' and self.current_chat in self.private_chats:
            user_local_ip = self.user_ips.get(self.current_chat_id, 'Неизвестно')
            user_server_ip = self.user_server_ips.get(self.current_chat_id, 'Неизвестно')
            self.chat_title.config(text=f"Личный чат с {self.current_chat_id} (локальный: {user_local_ip}, серверный: {user_server_ip})")

    def exit_app(self):
        """Выход из приложения"""
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
        self.root.destroy()
        sys.exit()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    client = MessengerClient()

    client.run()
