
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import time
import random
from dotenv import load_dotenv
import os

# Загрузка токена из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Общий лимит монет
TOTAL_COINS_LIMIT = 10_000_000_000
total_coins_mined = 0  # Отслеживается в базе данных

# Инициализация базы данных
def db_connection():
    return sqlite3.connect('iziswap.db')

# Функция для создания или получения пользователя
def get_or_create_user(user_id, username, ref_code=None):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ref_code FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if user is None:
        # Генерация уникального реферального кода
        ref_code = ref_code or f"ref{user_id}"
        cursor.execute(
            "INSERT INTO users (user_id, username, ref_code) VALUES (?, ?, ?)",
            (user_id, username, ref_code)
        )
        conn.commit()
    else:
        ref_code = user[0]

    conn.close()
    return ref_code

# Востановление энергии
def restore_energy(user_id):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT energy, energy_restore_rate, last_energy_restore_time FROM users WHERE user_id = ?", (user_id,))
    energy, restore_rate, last_restore_time = cursor.fetchone()
    current_time = int(time.time())

    if energy >= 2400:
        return energy  # Энергия на максимуме

    time_elapsed = current_time - last_restore_time
    energy_to_restore = (time_elapsed // 3600) * restore_rate
    new_energy = min(2400, energy + energy_to_restore)

    if energy_to_restore > 0:
        cursor.execute(
            "UPDATE users SET energy = ?, last_energy_restore_time = ? WHERE user_id = ?",
            (new_energy, current_time, user_id)
        )
        conn.commit()

    conn.close()
    return new_energy

# Ежедневный бонус
def daily_bonus(user_id):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT last_bonus_time FROM users WHERE user_id = ?", (user_id,))
    last_bonus_time = cursor.fetchone()[0]
    current_time = int(time.time())

    if current_time - last_bonus_time >= 86400:  # 24 часа
        cursor.execute("UPDATE users SET balance = balance + 50, last_bonus_time = ? WHERE user_id = ?", (current_time, user_id))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

# Покупка энергии
def buy_energy(user_id, ton_spent):
    conn = db_connection()
    cursor = conn.cursor()
    boost_energy = ton_spent * 100  # 100 энергии за 1 TON
    cursor.execute("SELECT energy_boost FROM users WHERE user_id = ?", (user_id,))
    current_boost = cursor.fetchone()[0]

    if current_boost + boost_energy > 50000:
        conn.close()
        return False  # Превышен лимит покупки энергии

    cursor.execute("UPDATE users SET energy_boost = energy_boost + ? WHERE user_id = ?", (boost_energy, user_id))
    conn.commit()
    conn.close()
    return True

# Обработка команды /start
@bot.message_handler(commands=['start'])
def start_game(message):
    user_id = message.chat.id
    username = message.from_user.username or "Аноним"
    ref_code = None

    if len(message.text.split()) > 1:
        ref_code = message.text.split()[1]

    user_ref_code = get_or_create_user(user_id, username, ref_code)

    # Начисление реферального бонуса
    if ref_code and ref_code != user_ref_code:
        conn = db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + 10 WHERE ref_code = ?", (ref_code,))
        conn.commit()
        conn.close()
        bot.send_message(user_id, "💸 Бонус 10 монет начислен вашему рефереру!")

    bot.send_message(user_id, f"Добро пожаловать в IZI SWAP, {username}! Ваш реферальный код: {user_ref_code}")
    send_game_buttons(user_id)

# Отправка кнопок игры
def send_game_buttons(chat_id):
    markup = InlineKeyboardMarkup()
    button_mine = InlineKeyboardButton("⛏ Клик для монет", callback_data="mine")
    button_bonus = InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="bonus")
    button_energy = InlineKeyboardButton("⚡ Проверить энергию", callback_data="energy")
    markup.add(button_mine, button_bonus, button_energy)
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)

# Обработка кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    user_id = call.message.chat.id

    if call.data == "mine":
        energy = restore_energy(user_id)
        if energy > 0:
            conn = db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET energy = energy - 1, balance = balance + 0.1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            bot.answer_callback_query(call.id, "Вы заработали 0.1 монет!")
        else:
            bot.answer_callback_query(call.id, "Недостаточно энергии!")

    elif call.data == "bonus":
        if daily_bonus(user_id):
            bot.answer_callback_query(call.id, "🎉 Вы получили ежедневный бонус в 50 монет!")
        else:
            bot.answer_callback_query(call.id, "⏳ Бонус доступен через 24 часа.")

    elif call.data == "energy":
        energy = restore_energy(user_id)
        bot.answer_callback_query(call.id, f"У вас {energy} энергии.")

# Запуск бота
if __name__ == "__main__":
    bot.polling()
