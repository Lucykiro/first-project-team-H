import socket
import threading
import json
import os
import logging
from datetime import datetime
import sys


class MessengerServer:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.clients = {}
        self.private_chats = {}
        self.group_chats = {}
        self.user_data = {}
        self.running = True

        self.setup_logging()
        self.load_data()

    def setup_logging(self):
        """Настройка подробного логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('server.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_data(self):
        """Загрузка сохраненных данных с улучшенной обработкой ошибок"""
        try:
            if os.path.exists('server_data.json'):
                with open('server_data.json', 'r', encoding='utf-8') as f:
                    content = f.read().strip()

                    # Проверяем, не пустой ли файл
                    if not content:
                        self.logger.warning("Файл данных пуст, используются значения по умолчанию")
                        self.private_chats = {}
                        self.group_chats = {}
                        self.user_data = {}
                        return

                    data = json.loads(content)
                    self.private_chats = data.get('private_chats', {})
                    self.group_chats = data.get('group_chats', {})
                    self.user_data = data.get('user_data', {})

                self.logger.info("Данные успешно загружены")

                # Конвертируем ключи private_chats обратно в tuple
                private_chats_converted = {}
                for key, value in self.private_chats.items():
                    if isinstance(key, list):
                        # Конвертируем list обратно в tuple
                        private_chats_converted[tuple(key)] = value
                    elif isinstance(key, str):
                        # Обрабатываем строковые ключи (для обратной совместимости)
                        try:
                            key_data = json.loads(key.replace("'", '"'))
                            private_chats_converted[tuple(key_data)] = value
                        except:
                            # Если не получается распарсить, пропускаем этот чат
                            self.logger.warning(f"Не удалось восстановить ключ личного чата: {key}")
                            continue
                    else:
                        private_chats_converted[key] = value

                self.private_chats = private_chats_converted
                self.logger.info(f"Загружено {len(self.private_chats)} личных чатов и {len(self.group_chats)} групп")

        except json.JSONDecodeError as e:
            self.logger.error(f"Ошибка декодирования JSON: {e}")
            self.logger.info("Создаются новые данные по умолчанию")
            # Создаем резервную копию поврежденного файлаh
            if os.path.exists('server_data.json'):
                backup_name = f"server_data_backup_{int(datetime.now().timestamp())}.json"
                os.rename('server_data.json', backup_name)
                self.logger.info(f"Создана резервная копия поврежденного файла: {backup_name}")

            self.private_chats = {}
            self.group_chats = {}
            self.user_data = {}

        except Exception as e:
            self.logger.error(f"Неожиданная ошибка загрузки данных: {e}")
            self.private_chats = {}
            self.group_chats = {}
            self.user_data = {}

    def save_data(self):
        """Сохранение данных с улучшенной обработкой ошибок"""
        try:
            # Создаем временную копию для безопасного сохранения
            temp_data = {
                'private_chats': {},
                'group_chats': self.group_chats.copy(),
                'user_data': self.user_data.copy()
            }

            # Конвертируем tuple ключи в строки для JSON сериализации
            for key, value in self.private_chats.items():
                if isinstance(key, tuple):
                    # Сохраняем tuple как JSON строку для надежности
                    temp_data['private_chats'][json.dumps(list(key))] = value
                else:
                    temp_data['private_chats'][str(key)] = value

            # Сначала сохраняем во временный файл
            temp_filename = 'server_data_temp.json'
            with open(temp_filename, 'w', encoding='utf-8') as f:
                json.dump(temp_data, f, indent=2, ensure_ascii=False, default=str)

            # Затем заменяем старый файл новым
            if os.path.exists('server_data.json'):
                os.replace(temp_filename, 'server_data.json')
            else:
                os.rename(temp_filename, 'server_data.json')

            self.logger.info(
                f"Данные успешно сохранены: {len(self.private_chats)} личных чатов, {len(self.group_chats)} групп")

        except Exception as e:
            self.logger.error(f"Ошибка сохранения данных: {e}")
            # Пытаемся удалить временный файл в случае ошибки
            try:
                if os.path.exists('server_data_temp.json'):
                    os.remove('server_data_temp.json')
            except:
                pass

    def get_user_local_ip(self, username):
        """Получение локального IP пользователя"""
        return self.user_data.get(username, {}).get('local_ip', 'Неизвестно')

    def get_user_server_ip(self, username):
        """Получение серверного IP пользователя"""
        return self.user_data.get(username, {}).get('server_ip', 'Неизвестно')

    def handle_client(self, client_socket, address):
        user_ip = address[0]  # Серверный IP (который видит сервер)
        username = None

        try:
            while self.running:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break

                message = json.loads(data)
                msg_type = message.get('type')

                if msg_type == 'register':
                    username = message['username']
                    local_ip = message.get('local_ip', 'Неизвестно')  # Локальный IP от клиента
                    
                    self.clients[username] = client_socket
                    self.user_data[username] = {
                        'local_ip': local_ip,      # Локальный IP компьютера
                        'server_ip': user_ip,      # Серверный IP (который видит сервер)
                        'last_seen': datetime.now().isoformat()
                    }
                    self.logger.info(f"Пользователь {username} зарегистрирован с локальным IP {local_ip} и серверным IP {user_ip}")

                    # Отправляем клиенту его серверный IP
                    server_ip_msg = {
                        'type': 'server_ip_assigned',
                        'server_ip': user_ip
                    }
                    client_socket.send(json.dumps(server_ip_msg).encode('utf-8'))

                    # Сохраняем данные после регистрации нового пользователя
                    self.save_data()

                    # Отправляем историю чатов пользователю
                    self.send_user_chats(username)

                elif msg_type == 'private_message':
                    from_user = message['from']
                    to_user = message['to']
                    text = message['text']
                    timestamp = datetime.now().isoformat()
                    local_ip = message.get('local_ip', self.get_user_local_ip(from_user))
                    server_ip = message.get('server_ip', self.get_user_server_ip(from_user))

                    chat_id = tuple(sorted([from_user, to_user]))
                    if chat_id not in self.private_chats:
                        self.private_chats[chat_id] = []

                    msg_data = {
                        'from': from_user,
                        'local_ip': local_ip,
                        'server_ip': server_ip,
                        'text': text,
                        'timestamp': timestamp
                    }
                    self.private_chats[chat_id].append(msg_data)

                    self.logger.info(f"Личное сообщение от {from_user} к {to_user}: {text[:50]}...")

                    # Отправляем сообщение получателю, если он онлайн
                    if to_user in self.clients:
                        forward_msg = {
                            'type': 'private_message',
                            'from': from_user,
                            'local_ip': local_ip,
                            'server_ip': server_ip,
                            'text': text,
                            'timestamp': timestamp
                        }
                        self.clients[to_user].send(
                            json.dumps(forward_msg, ensure_ascii=False).encode('utf-8')
                        )

                        # Обновляем список чатов получателя
                        self.send_user_chats(to_user)

                    # Также отправляем сообщение обратно отправителю для подтверждения
                    confirm_msg = {
                        'type': 'message_sent',
                        'message_id': message.get('message_id'),
                        'timestamp': timestamp
                    }
                    if from_user in self.clients:
                        self.clients[from_user].send(
                            json.dumps(confirm_msg).encode('utf-8')
                        )

                    self.save_data()

                elif msg_type == 'group_message':
                    from_user = message['from']
                    group_name = message['group']
                    text = message['text']
                    timestamp = datetime.now().isoformat()
                    local_ip = message.get('local_ip', self.get_user_local_ip(from_user))
                    server_ip = message.get('server_ip', self.get_user_server_ip(from_user))

                    if group_name in self.group_chats and from_user in self.group_chats[group_name]['members']:
                        msg_data = {
                            'from': from_user,
                            'local_ip': local_ip,
                            'server_ip': server_ip,
                            'text': text,
                            'timestamp': timestamp
                        }
                        self.group_chats[group_name]['messages'].append(msg_data)

                        self.logger.info(f"Групповое сообщение от {from_user} в {group_name}: {text[:50]}...")

                        # Рассылаем сообщение всем участникам группы
                        for member in self.group_chats[group_name]['members']:
                            if member in self.clients:
                                forward_msg = {
                                    'type': 'group_message',
                                    'from': from_user,
                                    'local_ip': local_ip,
                                    'server_ip': server_ip,
                                    'group': group_name,
                                    'text': text,
                                    'timestamp': timestamp
                                }
                                try:
                                    self.clients[member].send(
                                        json.dumps(forward_msg, ensure_ascii=False).encode('utf-8')
                                    )
                                except Exception as e:
                                    self.logger.error(f"Ошибка отправки сообщения пользователю {member}: {e}")

                        self.save_data()

                elif msg_type == 'create_group':
                    group_name = message['group_name']
                    creator = message['creator']

                    if group_name not in self.group_chats:
                        self.group_chats[group_name] = {
                            'creator': creator,
                            'members': [creator],
                            'messages': []
                        }
                        self.save_data()
                        self.logger.info(f"Создана группа {group_name} пользователем {creator}")

                        response = {'type': 'group_created', 'group_name': group_name}
                        client_socket.send(json.dumps(response).encode('utf-8'))

                        # Обновляем чаты у создателя
                        if creator in self.clients:
                            self.send_user_chats(creator)

                elif msg_type == 'join_group':
                    group_name = message['group_name']
                    username = message['username']

                    if group_name in self.group_chats:
                        if username not in self.group_chats[group_name]['members']:
                            self.group_chats[group_name]['members'].append(username)
                            self.save_data()
                            self.logger.info(f"Пользователь {username} вступил в группу {group_name}")

                            response = {'type': 'group_joined', 'group_name': group_name}
                            client_socket.send(json.dumps(response).encode('utf-8'))

                            # Обновляем чаты у пользователя
                            if username in self.clients:
                                self.send_user_chats(username)

                elif msg_type == 'get_chat_history':
                    chat_type = message['chat_type']
                    chat_id = message['chat_id']
                    username = message['username']

                    history = []
                    if chat_type == 'private':
                        chat_key = tuple(sorted([username, chat_id]))
                        if chat_key in self.private_chats:
                            history = self.private_chats[chat_key]
                    elif chat_type == 'group':
                        if chat_id in self.group_chats and username in self.group_chats[chat_id]['members']:
                            history = self.group_chats[chat_id]['messages']

                    response = {
                        'type': 'chat_history',
                        'chat_type': chat_type,
                        'chat_id': chat_id,
                        'history': history
                    }
                    client_socket.send(json.dumps(response, ensure_ascii=False).encode('utf-8'))

                elif msg_type == 'get_group_members':
                    """Обработка запроса списка участников группы"""
                    group_name = message['group_name']
                    username = message['username']

                    if group_name in self.group_chats and username in self.group_chats[group_name]['members']:
                        members = self.group_chats[group_name]['members']
                        # Создаем список участников с их IP-адресами
                        members_with_ip = []
                        for member in members:
                            # Получаем оба IP пользователя
                            member_local_ip = self.get_user_local_ip(member)
                            member_server_ip = self.get_user_server_ip(member)
                            
                            members_with_ip.append({
                                'username': member,
                                'local_ip': member_local_ip,
                                'server_ip': member_server_ip
                            })
                        
                        response = {
                            'type': 'group_members',
                            'group_name': group_name,
                            'members': members_with_ip
                        }
                        client_socket.send(json.dumps(response, ensure_ascii=False).encode('utf-8'))
                        self.logger.info(f"Пользователь {username} запросил список участников группы {group_name}")

                elif msg_type == 'rename_group':
                    group_name = message['group_name']
                    new_name = message['new_name']
                    username = message['username']

                    if (group_name in self.group_chats and
                            self.group_chats[group_name]['creator'] == username):

                        # Сохраняем данные группы под новым именем
                        self.group_chats[new_name] = self.group_chats.pop(group_name)
                        self.save_data()
                        self.logger.info(f"Группа {group_name} переименована в {new_name} пользователем {username}")

                        # Уведомляем всех участников группы
                        for member in self.group_chats[new_name]['members']:
                            if member in self.clients:
                                self.send_user_chats(member)

                elif msg_type == 'delete_group':
                    group_name = message['group_name']
                    username = message['username']

                    if (group_name in self.group_chats and
                            self.group_chats[group_name]['creator'] == username):

                        # Сохраняем список участников для уведомления
                        members = self.group_chats[group_name]['members'].copy()

                        # Удаляем группу
                        del self.group_chats[group_name]
                        self.save_data()
                        self.logger.info(f"Группа {group_name} удалена пользователем {username}")

                        # Уведомляем всех участников группы
                        for member in members:
                            if member in self.clients:
                                self.send_user_chats(member)

                elif msg_type == 'leave_group':
                    group_name = message['group_name']
                    username = message['username']

                    if (group_name in self.group_chats and
                            username in self.group_chats[group_name]['members']):

                        # Удаляем пользователя из группы
                        self.group_chats[group_name]['members'].remove(username)
                        self.save_data()
                        self.logger.info(f"Пользователь {username} покинул группу {group_name}")

                        # Обновляем чаты пользователя
                        if username in self.clients:
                            self.send_user_chats(username)

        except Exception as e:
            self.logger.error(f"Ошибка обработки клиента {address}: {e}")
        finally:
            if username and username in self.clients:
                del self.clients[username]
                self.logger.info(f"Пользователь {username} отключился")
            client_socket.close()

    def send_user_chats(self, username):
        """Отправляем пользователю список его чатов"""
        user_chats = {
            'type': 'chats_update',
            'private_chats': [],
            'group_chats': []
        }

        # Личные чаты
        for chat_id, messages in self.private_chats.items():
            if username in chat_id:
                other_user = chat_id[0] if chat_id[1] == username else chat_id[1]
                user_chats['private_chats'].append({
                    'user': other_user,
                    'local_ip': self.get_user_local_ip(other_user),
                    'server_ip': self.get_user_server_ip(other_user),
                    'last_message': messages[-1] if messages else None
                })

        # Групповые чаты
        for group_name, group_data in self.group_chats.items():
            if username in group_data['members']:
                user_chats['group_chats'].append({
                    'group_name': group_name,
                    'creator': group_data['creator'],
                    'last_message': group_data['messages'][-1] if group_data['messages'] else None
                })

        if username in self.clients:
            try:
                self.clients[username].send(
                    json.dumps(user_chats, ensure_ascii=False).encode('utf-8')
                )
            except Exception as e:
                self.logger.error(f"Ошибка отправки чатов пользователю {username}: {e}")

    def stop_server(self):
        """Остановка сервера"""
        self.logger.info("Остановка сервера...")
        self.running = False

        # Закрываем все клиентские соединения
        for username, sock in self.clients.items():
            try:
                sock.close()
            except:
                pass

        self.save_data()
        self.logger.info("Сервер остановлен")

    def console_handler(self):
        """Обработчик консольных команд"""
        while self.running:
            try:
                command = input().strip().lower()
                if command == 'stop':
                    self.stop_server()
                    os._exit(0)
                elif command == 'status':
                    self.logger.info(f"Статус: {len(self.clients)} подключенных пользователей")
                    self.logger.info(f"Личные чаты: {len(self.private_chats)}")
                    self.logger.info(f"Группы: {list(self.group_chats.keys())}")
                    self.logger.info(f"Пользователи: {list(self.user_data.keys())}")
                elif command == 'save':
                    self.save_data()
                    self.logger.info("Данные сохранены вручную")
                elif command == 'repair_data':
                    self.repair_data()
                else:
                    self.logger.info("Доступные команды: stop, status, save, repair_data")
            except Exception as e:
                self.logger.error(f"Ошибка в обработчике консоли: {e}")

    def repair_data(self):
        """Восстановление поврежденных данных"""
        self.logger.info("Попытка восстановления данных...")
        try:
            # Создаем резервную копию текущего файла
            if os.path.exists('server_data.json'):
                backup_name = f"server_data_repair_backup_{int(datetime.now().timestamp())}.json"
                os.rename('server_data.json', backup_name)
                self.logger.info(f"Создана резервная копия: {backup_name}")

            # Сбрасываем данные
            self.private_chats = {}
            self.group_chats = {}
            self.user_data = {}

            # Сохраняем новые данные
            self.save_data()
            self.logger.info("Данные успешно восстановлены")

        except Exception as e:
            self.logger.error(f"Ошибка восстановления данных: {e}")

    def start(self):
        """Запуск сервера"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            server_socket.settimeout(1)

            self.logger.info(f"Сервер запущен на {self.host}:{self.port}")
            self.logger.info("Доступные команды: stop, status, save, repair_data")

            # Запускаем обработчик консольных команд
            console_thread = threading.Thread(target=self.console_handler)
            console_thread.daemon = True
            console_thread.start()

            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.logger.error(f"Ошибка accept: {e}")

        except Exception as e:
            self.logger.error(f"Ошибка сервера: {e}")
        finally:
            server_socket.close()
            self.stop_server()


if __name__ == "__main__":
    server = MessengerServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop_server()