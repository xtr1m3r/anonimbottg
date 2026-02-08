import asyncio
import logging
import json
import os
from datetime import datetime, date
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "8507674114:AAFgjyi2r5MA5_L2BBqs5za0mxUN940Sk1Y"
ADMIN_IDS = [8525676787, 5503605811]  # Замените на ID администраторов
BLOCKED_FILE = "blocked_users.json"
POSTS_LOG = "posts_log.json"
USERS_LOG = "users_log.json"

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния
class AdminStates(StatesGroup):
    waiting_for_unblock_user = State()
    waiting_for_block_user = State()
    waiting_for_block_reason = State()
    waiting_for_reply = State()

# Менеджер блокировок
class BlockManager:
    def __init__(self, filename: str):
        self.filename = filename
        self.blocked_users = self.load_blocked()
        self.unblock_log = []
    
    def load_blocked(self) -> dict:
        """Загрузка списка заблокированных пользователей"""
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_blocked(self):
        """Сохранение списка заблокированных"""
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.blocked_users, f, ensure_ascii=False, indent=2)
    
    def block_user(self, user_id: int, username: str = "", 
                   first_name: str = "", last_name: str = "", 
                   admin_id: int = None, reason: str = ""):
        """Блокировка пользователя"""
        user_id_str = str(user_id)
        self.blocked_users[user_id_str] = {
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "blocked_at": datetime.now().isoformat(),
            "blocked_by": admin_id,
            "reason": reason
        }
        self.save_blocked()
        # Логируем блокировку
        self.log_block_unblock(user_id, "block", admin_id)
    
    def unblock_user(self, user_id: int, admin_id: int = None):
        """Разблокировка пользователя"""
        user_id_str = str(user_id)
        if user_id_str in self.blocked_users:
            del self.blocked_users[user_id_str]
            self.save_blocked()
            # Логируем разблокировку
            self.log_block_unblock(user_id, "unblock", admin_id)
            return True
        return False
    
    def log_block_unblock(self, user_id: int, action: str, admin_id: int = None):
        """Логирование блокировок/разблокировок"""
        log_entry = {
            "user_id": user_id,
            "action": action,
            "admin_id": admin_id,
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        self.unblock_log.append(log_entry)
    
    def get_today_stats(self) -> dict:
        """Получение статистики за сегодня"""
        today = datetime.now().strftime("%Y-%m-%d")
        blocked_today = [
            log for log in self.unblock_log 
            if log.get("date") == today and log["action"] == "block"
        ]
        unblocked_today = [
            log for log in self.unblock_log 
            if log.get("date") == today and log["action"] == "unblock"
        ]
        return {
            "blocked_today": len(blocked_today),
            "unblocked_today": len(unblocked_today)
        }
    
    def is_blocked(self, user_id: int) -> bool:
        """Проверка, заблокирован ли пользователь"""
        return str(user_id) in self.blocked_users
    
    def get_blocked_list(self) -> list:
        """Получение списка заблокированных"""
        return [
            {
                "user_id": int(uid),
                **data
            } for uid, data in self.blocked_users.items()
        ]

# Менеджер логов постов
class PostLogger:
    def __init__(self, filename: str):
        self.filename = filename
        self.logs = self.load_logs()
    
    def load_logs(self) -> list:
        """Загрузка логов"""
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save_logs(self):
        """Сохранение логов"""
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.logs, f, ensure_ascii=False, indent=2)
    
    def add_post(self, post_data: dict):
        """Добавление записи о посте"""
        self.logs.append(post_data)
        if len(self.logs) > 1000:  # Ограничение логов
            self.logs = self.logs[-1000:]
        self.save_logs()
    
    def get_today_stats(self) -> dict:
        """Получение статистики постов за сегодня"""
        today = datetime.now().date()
        today_posts = len([p for p in self.logs 
                          if datetime.fromisoformat(p['timestamp']).date() == today])
        return {"posts_today": today_posts}
    
    def get_user_info(self, user_id: int) -> dict:
        """Получение информации о пользователе из логов"""
        user_posts = [p for p in self.logs if p['user_id'] == user_id]
        if user_posts:
            latest_post = user_posts[-1]
            return {
                "user_id": user_id,
                "username": latest_post.get('username', ''),
                "first_name": latest_post.get('first_name', ''),
                "last_name": latest_post.get('last_name', ''),
                "total_posts": len(user_posts),
                "last_post": latest_post.get('timestamp')
            }
        return None

# Менеджер пользователей
class UserManager:
    def __init__(self, filename: str):
        self.filename = filename
        self.users = self.load_users()
    
    def load_users(self) -> dict:
        """Загрузка данных о пользователях"""
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_users(self):
        """Сохранение данных о пользователях"""
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)
    
    def add_user(self, user_id: int, username: str = "", 
                 first_name: str = "", last_name: str = ""):
        """Добавление нового пользователя"""
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            self.users[user_id_str] = {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
                "joined_date": datetime.now().strftime("%Y-%m-%d")
            }
        else:
            self.users[user_id_str]["last_seen"] = datetime.now().isoformat()
            if username:
                self.users[user_id_str]["username"] = username
            if first_name:
                self.users[user_id_str]["first_name"] = first_name
            if last_name:
                self.users[user_id_str]["last_name"] = last_name
        
        self.save_users()
    
    def get_today_stats(self) -> dict:
        """Получение статистики новых пользователей за сегодня"""
        today = datetime.now().strftime("%Y-%m-%d")
        new_today = len([
            uid for uid, data in self.users.items() 
            if data.get("joined_date") == today
        ])
        return {"new_users_today": new_today}
    
    def get_user_info(self, user_id: int) -> dict:
        """Получение информации о пользователе"""
        user_id_str = str(user_id)
        if user_id_str in self.users:
            return {
                "user_id": user_id,
                **self.users[user_id_str]
            }
        return None

# Инициализация менеджеров
block_manager = BlockManager(BLOCKED_FILE)
post_logger = PostLogger(POSTS_LOG)
user_manager = UserManager(USERS_LOG)

# Хранилище для сообщений, ожидающих ответа
reply_storage = {}

async def send_post_to_admins(message: Message, user: types.User):
    """Отправка поста администраторам в одном сообщении"""
    
    # Создаем подпись с информацией об отправителе
    sender_info = (
        f"💬 Сообщение от пользователя\n\n"
        f"👤 Пользователь:\n"
        f"🆔 ID: {user.id}\n"
        f"📛 Имя: {user.first_name or 'Не указано'}\n"
        f"📛 Фамилия: {user.last_name or 'Не указано'}\n"
        f"🔗 Username: @{user.username if user.username else 'Нет'}\n"
        f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📝 Сообщение:"
    )
    
    # Добавляем сообщение пользователя
    if message.text:
        full_text = f"{sender_info}\n\n{message.text}"
    elif message.caption:
        full_text = f"{sender_info}\n\n{message.caption}"
    else:
        full_text = f"{sender_info}\n\n[Медиа-сообщение]"
    
    # Создаем кнопку "Ответить" для админов
    reply_button = InlineKeyboardButton(
        text="💬 Ответить", 
        callback_data=f"reply_{user.id}"
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[reply_button]])
    
    # Логируем пост
    post_data = {
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "content": message.text or message.caption or "",
        "media_type": message.content_type,
        "timestamp": datetime.now().isoformat(),
        "message_id": message.message_id,
        "chat_id": message.chat.id
    }
    post_logger.add_post(post_data)
    
    # Отправляем админам в зависимости от типа контента
    sent_messages = []
    for admin_id in ADMIN_IDS:
        try:
            if message.text:
                sent_msg = await bot.send_message(
                    admin_id,
                    full_text,
                    reply_markup=admin_kb
                )
                sent_messages.append(sent_msg.message_id)
            elif message.photo:
                sent_msg = await bot.send_photo(
                    admin_id,
                    message.photo[-1].file_id,
                    caption=full_text,
                    reply_markup=admin_kb
                )
                sent_messages.append(sent_msg.message_id)
            elif message.video:
                sent_msg = await bot.send_video(
                    admin_id,
                    message.video.file_id,
                    caption=full_text,
                    reply_markup=admin_kb
                )
                sent_messages.append(sent_msg.message_id)
            elif message.document:
                sent_msg = await bot.send_document(
                    admin_id,
                    message.document.file_id,
                    caption=full_text,
                    reply_markup=admin_kb
                )
                sent_messages.append(sent_msg.message_id)
            elif message.voice:
                # Для голосовых сначала отправляем текст, потом голосовое
                sent_msg = await bot.send_message(
                    admin_id,
                    full_text,
                    reply_markup=admin_kb
                )
                sent_messages.append(sent_msg.message_id)
                await bot.send_voice(admin_id, message.voice.file_id)
            elif message.audio:
                sent_msg = await bot.send_audio(
                    admin_id,
                    message.audio.file_id,
                    caption=full_text,
                    reply_markup=admin_kb
                )
                sent_messages.append(sent_msg.message_id)
            elif message.sticker:
                # Для стикеров сначала отправляем информацию, потом стикер
                sent_msg = await bot.send_message(
                    admin_id,
                    full_text,
                    reply_markup=admin_kb
                )
                sent_messages.append(sent_msg.message_id)
                await bot.send_sticker(admin_id, message.sticker.file_id)
            else:
                # Для других типов сообщений
                sent_msg = await bot.send_message(
                    admin_id,
                    full_text,
                    reply_markup=admin_kb
                )
                sent_messages.append(sent_msg.message_id)
                
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")
            # Попробуем отправить простым текстом в случае ошибки
            try:
                sent_msg = await bot.send_message(
                    admin_id,
                    f"{sender_info}\n\n⚠️ Не удалось отправить медиа. Тип: {message.content_type}",
                    reply_markup=admin_kb
                )
                sent_messages.append(sent_msg.message_id)
            except Exception as e2:
                logger.error(f"Не удалось отправить даже текст админу {admin_id}: {e2}")
    
    # Сохраняем информацию о сообщении для возможного ответа
    reply_storage[str(user.id)] = {
        "user_id": user.id,
        "message_ids": sent_messages,
        "timestamp": datetime.now().isoformat()
    }

async def send_reply_to_user(user_id: int, message: Message, admin_user: types.User):
    """Отправка ответа пользователю - только "Ответ от администратора" и сообщение"""
    
    # Формируем только надпись и сообщение
    if message.text:
        full_text = f"💬 Ответ от администратора\n\n{message.text}"
    elif message.caption:
        full_text = f"💬 Ответ от администратора\n\n{message.caption}"
    else:
        full_text = f"💬 Ответ от администратора\n\n[Медиа-сообщение]"
    
    # Создаем кнопку "Ответить" для пользователя
    reply_button = InlineKeyboardButton(
        text="💬 Ответить", 
        callback_data=f"reply_{admin_user.id}"
    )
    reply_kb = InlineKeyboardMarkup(inline_keyboard=[[reply_button]])
    
    try:
        if message.text:
            await bot.send_message(
                user_id,
                full_text,
                reply_markup=reply_kb
            )
            return True
        elif message.photo:
            await bot.send_photo(
                user_id,
                message.photo[-1].file_id,
                caption=full_text,
                reply_markup=reply_kb
            )
            return True
        elif message.video:
            await bot.send_video(
                user_id,
                message.video.file_id,
                caption=full_text,
                reply_markup=reply_kb
            )
            return True
        elif message.document:
            await bot.send_document(
                user_id,
                message.document.file_id,
                caption=full_text,
                reply_markup=reply_kb
            )
            return True
        elif message.voice:
            # Для голосовых сначала текст, потом голосовое
            await bot.send_message(
                user_id,
                full_text,
                reply_markup=reply_kb
            )
            await bot.send_voice(user_id, message.voice.file_id)
            return True
        elif message.audio:
            await bot.send_audio(
                user_id,
                message.audio.file_id,
                caption=full_text,
                reply_markup=reply_kb
            )
            return True
        elif message.sticker:
            # Для стикеров сначала информация, потом стикер
            await bot.send_message(
                user_id,
                full_text,
                reply_markup=reply_kb
            )
            await bot.send_sticker(user_id, message.sticker.file_id)
            return True
        else:
            await bot.send_message(
                user_id,
                full_text,
                reply_markup=reply_kb
            )
            return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки ответа пользователю {user_id}: {e}")
        return False

async def send_reply_to_admin(admin_id: int, message: Message, user: types.User):
    """Отправка ответа администратору - с полной информацией о пользователе"""
    
    # Формируем информацию о пользователе
    user_info = (
        f"💬 Ответ от пользователя\n\n"
        f"👤 Пользователь:\n"
        f"🆔 ID: {user.id}\n"
        f"📛 Имя: {user.first_name or 'Не указано'}\n"
        f"📛 Фамилия: {user.last_name or 'Не указано'}\n"
        f"🔗 Username: @{user.username if user.username else 'Нет'}\n"
        f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📝 Сообщение:"
    )
    
    # Добавляем сообщение пользователя
    if message.text:
        full_text = f"{user_info}\n\n{message.text}"
    elif message.caption:
        full_text = f"{user_info}\n\n{message.caption}"
    else:
        full_text = f"{user_info}\n\n[Медиа-сообщение]"
    
    # Кнопка для ответа
    reply_button = InlineKeyboardButton(
        text="💬 Ответить", 
        callback_data=f"reply_{user.id}"
    )
    reply_kb = InlineKeyboardMarkup(inline_keyboard=[[reply_button]])
    
    try:
        if message.text:
            await bot.send_message(
                admin_id,
                full_text,
                reply_markup=reply_kb
            )
            return True
        elif message.photo:
            await bot.send_photo(
                admin_id,
                message.photo[-1].file_id,
                caption=full_text,
                reply_markup=reply_kb
            )
            return True
        elif message.video:
            await bot.send_video(
                admin_id,
                message.video.file_id,
                caption=full_text,
                reply_markup=reply_kb
            )
            return True
        elif message.document:
            await bot.send_document(
                admin_id,
                message.document.file_id,
                caption=full_text,
                reply_markup=reply_kb
            )
            return True
        elif message.voice:
            await bot.send_message(
                admin_id,
                full_text,
                reply_markup=reply_kb
            )
            await bot.send_voice(admin_id, message.voice.file_id)
            return True
        elif message.audio:
            await bot.send_audio(
                admin_id,
                message.audio.file_id,
                caption=full_text,
                reply_markup=reply_kb
            )
            return True
        elif message.sticker:
            await bot.send_message(
                admin_id,
                full_text,
                reply_markup=reply_kb
            )
            await bot.send_sticker(admin_id, message.sticker.file_id)
            return True
        else:
            await bot.send_message(
                admin_id,
                full_text,
                reply_markup=reply_kb
            )
            return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки ответа администратору {admin_id}: {e}")
        return False

# Команда /start
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user = message.from_user
    
    # Добавляем пользователя в базу
    user_manager.add_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    if block_manager.is_blocked(user_id):
        await message.answer("❌ Вы заблокированы и не можете отправлять сообщения.")
        return
    
    # Приветственное сообщение
    welcome_text = (
        "👋 Привет! Я бот для анонимных предложок.\n\n"
        "📝 Просто отправьте мне сообщение, и оно будет переслано администраторам "
        "анонимно (ваши данные не будут видны другим пользователям, но будут доступны админам).\n\n"
        "⚠️ Пожалуйста, соблюдайте правила сообщества."
    )
    
    # Для администраторов добавляем информацию о панели
    if user_id in ADMIN_IDS:
        welcome_text += "\n\n👑 Вы администратор. Используйте /panell для открытия панели управления."
    
    await message.answer(welcome_text)

# Команда /panell - Панель администратора
@dp.message(Command("panell"))
async def admin_panel_command(message: Message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав администратора.")
        return
    
    # Создаем клавиатуру админ панели
    admin_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚫 Заблокировать пользователя")],
            [KeyboardButton(text="✅ Разблокировать пользователя")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="✖️ Закрыть меню")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    
    await message.answer("👑 Панель администратора", reply_markup=admin_kb)

# Команда /closee - Закрыть меню админа
@dp.message(Command("closee"))
async def close_admin_menu(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав администратора.")
        return
    
    # Очищаем состояние ответа, если оно есть
    current_state = await state.get_state()
    if current_state == AdminStates.waiting_for_reply:
        await state.clear()
        await message.answer("✅ Ответ отменен.")
    
    # Удаляем клавиатуру
    remove_kb = types.ReplyKeyboardRemove()
    await message.answer("✅ Меню администратора закрыто", reply_markup=remove_kb)

# Обработка кнопок админ панели
@dp.message(F.text == "✖️ Закрыть меню")
async def close_menu_button(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    # Очищаем состояние ответа, если оно есть
    current_state = await state.get_state()
    if current_state == AdminStates.waiting_for_reply:
        await state.clear()
        await message.answer("✅ Ответ отменен.")
    
    # Удаляем клавиатуру
    remove_kb = types.ReplyKeyboardRemove()
    await message.answer("✅ Меню администратора закрыто", reply_markup=remove_kb)

# Кнопка "Разблокировать пользователя"
@dp.message(F.text == "✅ Разблокировать пользователя")
async def unblock_user_button(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    # Очищаем состояние ответа, если оно есть
    current_state = await state.get_state()
    if current_state == AdminStates.waiting_for_reply:
        await state.clear()
    
    # Получаем список заблокированных пользователей
    blocked_list = block_manager.get_blocked_list()
    
    if not blocked_list:
        await message.answer("✅ Нет заблокированных пользователей.")
        return
    
    # Формируем сообщение со списком
    text = "🚫 Заблокированные пользователи (выберите ID для разблокировки):\n\n"
    for user in blocked_list:
        blocked_at = datetime.fromisoformat(user['blocked_at']).strftime('%d.%m.%Y')
        name = f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
        reason = user.get('reason', 'Причина не указана')
        text += f"🆔 {user['user_id']} - 👤 {name or 'Без имени'}\n"
        text += f"   📝 Причина: {reason}\n"
        text += f"   🕒 Заблокирован: {blocked_at}\n\n"
    
    text += "📝 Отправьте ID пользователя для разблокировки:"
    
    await message.answer(text)
    await state.set_state(AdminStates.waiting_for_unblock_user)

# Обработка ID для разблокировки
@dp.message(AdminStates.waiting_for_unblock_user)
async def handle_unblock_user_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    try:
        user_id_to_unblock = int(message.text.strip())
        
        # Получаем информацию о пользователе
        blocked_list = block_manager.get_blocked_list()
        user_info = next((u for u in blocked_list if u['user_id'] == user_id_to_unblock), None)
        
        if user_info:
            # Разблокируем пользователя
            success = block_manager.unblock_user(user_id_to_unblock, admin_id=message.from_user.id)
            
            if success:
                name = f"{user_info['first_name'] or ''} {user_info['last_name'] or ''}".strip()
                reason = user_info.get('reason', 'Причина не указана')
                await message.answer(
                    f"✅ Пользователь успешно разблокирован:\n\n"
                    f"🆔 ID: {user_id_to_unblock}\n"
                    f"👤 Имя: {name or 'Без имени'}\n"
                    f"📝 Причина блокировки: {reason}"
                )
                
                # Пытаемся уведомить пользователя
                try:
                    await bot.send_message(
                        user_id_to_unblock,
                        "✅ Вы были разблокированы администратором."
                    )
                except Exception as e:
                    logger.error(f"Не удалось уведомить пользователя {user_id_to_unblock}: {e}")
            else:
                await message.answer("❌ Пользователь не был заблокирован.")
        else:
            await message.answer("❌ Пользователь с таким ID не найден в списке заблокированных.")
    
    except ValueError:
        await message.answer("⚠️ Неверный формат ID. Отправьте числовой ID пользователя.")
    
    await state.clear()

# Кнопка "Заблокировать пользователя"
@dp.message(F.text == "🚫 Заблокировать пользователя")
async def block_user_button(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    # Очищаем состояние ответа, если оно есть
    current_state = await state.get_state()
    if current_state == AdminStates.waiting_for_reply:
        await state.clear()
    
    await message.answer("📝 Отправьте ID пользователя для блокировки:")
    await state.set_state(AdminStates.waiting_for_block_user)

# Обработка ID для блокировки
@dp.message(AdminStates.waiting_for_block_user)
async def handle_block_user_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    try:
        user_id_to_block = int(message.text.strip())
        
        # Проверяем, не пытаемся ли заблокировать админа
        if user_id_to_block in ADMIN_IDS:
            await message.answer("❌ Нельзя заблокировать администратора.")
            await state.clear()
            return
        
        # Проверяем, не заблокирован ли уже пользователь
        if block_manager.is_blocked(user_id_to_block):
            await message.answer("⚠️ Этот пользователь уже заблокирован.")
            await state.clear()
            return
        
        # Сохраняем ID пользователя и запрашиваем причину
        await state.update_data(block_user_id=user_id_to_block)
        await message.answer("📝 Теперь отправьте причину блокировки:")
        await state.set_state(AdminStates.waiting_for_block_reason)
    
    except ValueError:
        await message.answer("⚠️ Неверный формат ID. Отправьте числовой ID пользователя.")
        await state.clear()

# Обработка причины блокировки
@dp.message(AdminStates.waiting_for_block_reason)
async def handle_block_reason(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    user_data = await state.get_data()
    user_id_to_block = user_data.get('block_user_id')
    reason = message.text.strip()
    
    if not reason:
        await message.answer("⚠️ Причина не может быть пустой. Попробуйте снова.")
        return
    
    # Получаем информацию о пользователе
    user_info = user_manager.get_user_info(user_id_to_block)
    
    if user_info:
        # Блокируем пользователя с указанием причины
        block_manager.block_user(
            user_id=user_id_to_block,
            username=user_info.get('username', ''),
            first_name=user_info.get('first_name', ''),
            last_name=user_info.get('last_name', ''),
            admin_id=message.from_user.id,
            reason=reason
        )
        
        name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
        await message.answer(
            f"✅ Пользователь успешно заблокирован:\n\n"
            f"🆔 ID: {user_id_to_block}\n"
            f"👤 Имя: {name or 'Без имени'}\n"
            f"📝 Причина: {reason}"
        )
        
        # Пытаемся уведомить пользователя
        try:
            await bot.send_message(
                user_id_to_block,
                f"🚫 Вы были заблокированы администратором.\n"
                f"📝 Причина: {reason}"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id_to_block}: {e}")
    else:
        # Если пользователь не найден в базе, все равно блокируем
        block_manager.block_user(
            user_id=user_id_to_block,
            username="",
            first_name="",
            last_name="",
            admin_id=message.from_user.id,
            reason=reason
        )
        await message.answer(
            f"✅ Пользователь успешно заблокирован:\n\n"
            f"🆔 ID: {user_id_to_block}\n"
            f"📝 Причина: {reason}\n"
            f"ℹ️ Пользователь не найден в базе данных"
        )
    
    await state.clear()

# Кнопка "Статистика"
@dp.message(F.text == "📊 Статистика")
async def show_stats_button(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    # Очищаем состояние ответа, если оно есть
    current_state = await state.get_state()
    if current_state == AdminStates.waiting_for_reply:
        await state.clear()
    
    # Получаем статистику за сегодня
    user_stats = user_manager.get_today_stats()
    block_stats = block_manager.get_today_stats()
    post_stats = post_logger.get_today_stats()
    
    # Получаем общую статистику
    total_users = len(user_manager.users)
    total_blocked = len(block_manager.blocked_users)
    total_posts = len(post_logger.logs)
    
    # Формируем сообщение со статистикой
    stats_text = (
        "📊 Статистика за сегодня:\n"
        f"┣ 👤 Новые пользователи: {user_stats.get('new_users_today', 0)}\n"
        f"┣ 🚫 Заблокированные: {block_stats.get('blocked_today', 0)}\n"
        f"┣ ✅ Разблокированные: {block_stats.get('unblocked_today', 0)}\n"
        f"┗ 📨 Постов отправлено: {post_stats.get('posts_today', 0)}\n\n"
        
        "📈 Общая статистика:\n"
        f"┣ 👥 Всего пользователей: {total_users}\n"
        f"┣ 🚫 Всего заблокировано: {total_blocked}\n"
        f"┗ 📨 Всего постов: {total_posts}\n\n"
        
        f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    await message.answer(stats_text)

# Обработка сообщений от пользователей (не админов)
@dp.message(F.from_user.id.not_in(ADMIN_IDS))
async def handle_user_message(message: Message, state: FSMContext):
    """Обработка всех сообщений от пользователей (не админов)"""
    user_id = message.from_user.id
    user = message.from_user
    
    # Обновляем информацию о пользователе
    user_manager.add_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Проверка на блокировку
    if block_manager.is_blocked(user_id):
        await message.answer("❌ Вы заблокированы и не можете отправлять сообщения.")
        return
    
    # Проверяем, не находится ли пользователь в состоянии ожидания ответа
    current_state = await state.get_state()
    if current_state == AdminStates.waiting_for_reply:
        # Пользователь отвечает администратору
        state_data = await state.get_data()
        admin_id = state_data.get('reply_to_admin')
        
        if admin_id:
            try:
                # Отправляем ответ администратору
                success = await send_reply_to_admin(admin_id, message, user)
                
                if success:
                    await message.answer("✅ Ваш ответ отправлен администратору.")
                    await state.clear()
                else:
                    await message.answer("❌ Не удалось отправить ответ администратору.")
                
            except Exception as e:
                logger.error(f"Ошибка отправки ответа администратору {admin_id}: {e}")
                await message.answer("❌ Не удалось отправить ответ администратору.")
        else:
            await state.clear()
            await send_post_to_admins(message, user)
            await message.answer("✅ Ваш пост отправлен администраторам анонимно!")
    else:
        # Если пользователь не отвечает, отправляем как обычную предложку
        await send_post_to_admins(message, user)
        await message.answer("✅ Ваш пост отправлен администраторам анонимно!")

# Обработка сообщений от администраторов
@dp.message(F.from_user.id.in_(ADMIN_IDS))
async def handle_admin_message(message: Message, state: FSMContext):
    """Обработка всех сообщений от администраторов"""
    admin_id = message.from_user.id
    
    # Проверяем, находится ли админ в состоянии ожидания ответа
    current_state = await state.get_state()
    if current_state == AdminStates.waiting_for_reply:
        # Админ отвечает пользователю
        state_data = await state.get_data()
        reply_to_user_id = state_data.get('reply_to_user')
        
        if reply_to_user_id:
            # Проверяем, не заблокирован ли пользователь
            if block_manager.is_blocked(reply_to_user_id):
                await message.answer("❌ Этот пользователь заблокирован.")
                await state.clear()
                return
            
            # Отправляем ответ пользователю
            success = await send_reply_to_user(reply_to_user_id, message, message.from_user)
            
            if success:
                await message.answer(f"✅ Ответ отправлен пользователю {reply_to_user_id}")
                await state.clear()
            else:
                await message.answer("❌ Не удалось отправить ответ пользователю.")
        else:
            await state.clear()
            await message.answer("❌ Ошибка: не найден пользователь для ответа.")

# Обработка callback кнопки "Ответить"
@dp.callback_query(F.data.startswith("reply_"))
async def reply_to_user_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    target_user_id = int(callback.data.split("_")[1])
    
    # Проверяем, не заблокирован ли текущий пользователь
    if block_manager.is_blocked(user_id):
        await callback.answer("❌ Вы заблокированы и не можете отвечать на сообщения.", show_alert=True)
        return
    
    # Проверяем, не заблокирован ли целевой пользователь
    if block_manager.is_blocked(target_user_id):
        await callback.answer("❌ Этот пользователь заблокирован.", show_alert=True)
        return
    
    if user_id in ADMIN_IDS:
        # Админ отвечает пользователю
        # Сохраняем ID пользователя, которому отвечаем
        await state.set_state(AdminStates.waiting_for_reply)
        await state.update_data(reply_to_user=target_user_id)
        
        # Получаем информацию о пользователе
        user_info = user_manager.get_user_info(target_user_id)
        name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip() if user_info else "Без имени"
        
        await callback.message.answer(
            f"💬 Вы отвечаете пользователю:\n\n"
            f"🆔 ID: {target_user_id}\n"
            f"👤 Имя: {name}\n\n"
            f"📝 Отправьте сообщение для ответа (текст, фото, видео и т.д.):\n\n"
            f"ℹ️ Чтобы отменить ответ, используйте /closee"
        )
        
        await callback.answer(f"Отвечаете пользователю {target_user_id}")
    else:
        # Пользователь отвечает администратору
        # Проверяем, что целевой пользователь - администратор
        if target_user_id not in ADMIN_IDS:
            await callback.answer("❌ Вы можете отвечать только администраторам.", show_alert=True)
            return
        
        # Переводим пользователя в состояние ожидания ответа
        await state.set_state(AdminStates.waiting_for_reply)
        await state.update_data(reply_to_admin=target_user_id)
        
        await callback.message.answer(
            f"💬 Вы отвечаете администратору.\n\n"
            f"📝 Отправьте ваше сообщение:\n\n"
            f"ℹ️ Чтобы отправить обычное сообщение администраторам, используйте /start"
        )
        
        await callback.answer("Отвечаете администратору")

# Запуск бота
async def main():
    # Создаем файлы если их нет
    for filename in [BLOCKED_FILE, POSTS_LOG, USERS_LOG]:
        if not os.path.exists(filename):
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({} if filename != POSTS_LOG else [], f)
    
    logger.info("Бот запущен...")
    
    # Убедимся, что ADMIN_IDS содержит реальные ID
    logger.info(f"Администраторы: {ADMIN_IDS}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())