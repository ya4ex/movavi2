import asyncio
import logging
import random

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = "8124381179:AAEX5dZEXWfQ3y5lR-ECQBY9QhDH9CXFZQ0"

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

USERS = {}
PRODUCTS = []
ORDERS = {}
MESSAGES = {}

class Registration(StatesGroup):
    username = State()
    password = State()

class ProductCreate(StatesGroup):
    category = State()
    description = State()
    method = State()
    bank = State()
    details = State()

class ReviewState(StatesGroup):
    comment = State()

class OrderState(StatesGroup):
    screenshot = State()

class ChatState(StatesGroup):
    waiting_message = State()

def welcome_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔐 Регистрация"),
                KeyboardButton(text="🔑 Авторизация")
            ]
        ],
        resize_keyboard=True
    )

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🛍️ Каталог"),
                KeyboardButton(text="➕ Продать")
            ],
            [
                KeyboardButton(text="📂 Мои товары"),
                KeyboardButton(text="👤 Профиль")
            ],
            [
                KeyboardButton(text="💬 Сообщения"),
                KeyboardButton(text="📊 Статистика")
            ],
            [
                KeyboardButton(text="❤️ Донат"),
                KeyboardButton(text="ℹ️ О сервисе")
            ]
        ],
        resize_keyboard=True
    )

def categories_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📱 Telegram"),
                KeyboardButton(text="🎮 Игры")
            ],
            [
                KeyboardButton(text="📦 Другое")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )

def methods_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📲 СБП")
            ],
            [
                KeyboardButton(text="💳 Карта")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )

def banks_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🟩 Сбербанк"),
                KeyboardButton(text="🟨 Т-Банк")
            ],
            [
                KeyboardButton(text="🟦 ВТБ"),
                KeyboardButton(text="🟥 Альфа-Банк")
            ],
            [
                KeyboardButton(text="🏛️ Другой")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "🌊 Добро пожаловать в Sea Pay\n\n"
        "Маркетплейс игровых товаров",
        reply_markup=welcome_keyboard()
    )

@dp.message(F.text == "🔐 Регистрация")
async def registration_start(message: Message, state: FSMContext):
    await state.set_state(Registration.username)

    await message.answer(
        "📝 Введите логин\n"
        "7 английских букв"
    )

@dp.message(Registration.username)
async def registration_username(message: Message, state: FSMContext):
    username = message.text.strip()

    if len(username) != 7 or not username.isalpha():
        await message.answer(
            "❌ Логин должен содержать 7 букв"
        )
        return

    await state.update_data(username=username)

    await state.set_state(Registration.password)

    await message.answer(
        "🔑 Введите пароль\n"
        "10 символов"
    )

@dp.message(Registration.password)
async def registration_password(message: Message, state: FSMContext):
    password = message.text.strip()

    if len(password) != 10:
        await message.answer(
            "❌ Пароль должен содержать 10 символов"
        )
        return

    data = await state.get_data()

    USERS[message.from_user.id] = {
        "username": data["username"],
        "password": password
    }

    await state.clear()

    await message.answer(
        "✅ Регистрация завершена",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "🔑 Авторизация")
async def auth(message: Message):
    if message.from_user.id not in USERS:
        await message.answer(
            "❌ Аккаунт не найден"
        )
        return

    await message.answer(
        "✅ Авторизация успешна",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "👤 Профиль")
async def profile(message: Message):
    user = USERS.get(message.from_user.id)

    if not user:
        await message.answer(
            "❌ Сначала зарегистрируйтесь"
        )
        return

    products = [
        p for p in PRODUCTS
        if p["seller_id"] == message.from_user.id
    ]

    await message.answer(
        f"👤 Профиль\n\n"
        f"🆔 Логин: {user['username']}\n"
        f"📦 Товаров: {len(products)}\n"
        f"⭐ Рейтинг: 5.0"
    )

@dp.message(F.text == "📊 Статистика")
async def statistics(message: Message):
    await message.answer(
        f"📊 Статистика Sea Pay\n\n"
        f"👥 Пользователей: {len(USERS)}\n"
        f"📦 Товаров: {len(PRODUCTS)}\n"
        f"🛡️ Сделок: 61"
    )

@dp.message(F.text == "ℹ️ О сервисе")
async def about(message: Message):
    await message.answer(
        "🌊 Sea Pay — p2p маркетплейс игровых товаров."
    )

@dp.message(F.text == "❤️ Донат")
async def donate(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💸 Поддержать",
                    url="https://t.me/send?start=IVzGwn2pggSS"
                )
            ]
        ]
    )

    await message.answer(
        "❤️ Спасибо за поддержку проекта",
        reply_markup=keyboard
    )

@dp.message(F.text == "➕ Продать")
async def create_product_start(message: Message, state: FSMContext):
    if message.from_user.id not in USERS:
        await message.answer(
            "❌ Сначала зарегистрируйтесь"
        )
        return

    await state.set_state(ProductCreate.category)

    await message.answer(
        "📂 Выберите категорию",
        reply_markup=categories_keyboard()
    )

@dp.message(ProductCreate.category)
async def create_product_category(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()

        await message.answer(
            "🏠 Главное меню",
            reply_markup=main_keyboard()
        )
        return

    await state.update_data(category=message.text)

    await state.set_state(ProductCreate.description)

    await message.answer(
        "📝 Опишите товар"
    )

@dp.message(ProductCreate.description)
async def create_product_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)

    await state.set_state(ProductCreate.method)

    await message.answer(
        "💳 Выберите способ оплаты",
        reply_markup=methods_keyboard()
    )

@dp.message(ProductCreate.method)
async def create_product_method(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()

        await message.answer(
            "🏠 Главное меню",
            reply_markup=main_keyboard()
        )
        return

    await state.update_data(method=message.text)

    await state.set_state(ProductCreate.bank)

    await message.answer(
        "🏛️ Выберите банк",
        reply_markup=banks_keyboard()
    )

@dp.message(ProductCreate.bank)
async def create_product_bank(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()

        await message.answer(
            "🏠 Главное меню",
            reply_markup=main_keyboard()
        )
        return

    await state.update_data(bank=message.text)

    await state.set_state(ProductCreate.details)

    await message.answer(
        "💳 Введите реквизиты"
    )

@dp.message(ProductCreate.details)
async def create_product_details(message: Message, state: FSMContext):
    data = await state.get_data()

    product = {
        "id": len(PRODUCTS) + 1,
        "seller_id": message.from_user.id,
        "seller_name": USERS[message.from_user.id]["username"],
        "category": data["category"],
        "description": data["description"],
        "method": data["method"],
        "bank": data["bank"],
        "details": message.text,
        "reviews": []
    }

    PRODUCTS.append(product)

    await state.clear()

    await message.answer(
        "✅ Товар опубликован",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "📂 Мои товары")
async def my_products(message: Message):
    products = [
        p for p in PRODUCTS
        if p["seller_id"] == message.from_user.id
    ]

    if not products:
        await message.answer(
            "📭 У вас нет товаров"
        )
        return

    for product in products:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🗑️ Удалить",
                        callback_data=f"delete_{product['id']}"
                    )
                ]
            ]
        )

        await message.answer(
            f"📦 Лот #{product['id']}\n\n"
            f"📂 Категория: {product['category']}\n"
            f"📝 Описание: {product['description']}",
            reply_markup=keyboard
        )

@dp.callback_query(F.data.startswith("delete_"))
async def delete_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])

    product = next(
        (
            p for p in PRODUCTS
            if p["id"] == product_id
            and p["seller_id"] == callback.from_user.id
        ),
        None
    )

    if not product:
        await callback.answer(
            "❌ Товар не найден",
            show_alert=True
        )
        return

    PRODUCTS.remove(product)

    await callback.message.edit_text(
        f"🗑️ Лот #{product_id} удален"
    )

    await callback.answer()

@dp.message(F.text == "🛍️ Каталог")
async def catalog(message: Message):
    if not PRODUCTS:
        await message.answer(
            "📭 Каталог пуст"
        )
        return

    for product in PRODUCTS:

        reviews_text = ""

        if product["reviews"]:
            reviews_text = "\n\n💬 Отзывы:\n" + "\n".join(product["reviews"])

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💳 Купить",
                        callback_data=f"buy_{product['id']}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✍️ Отзыв",
                        callback_data=f"review_{product['id']}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="💬 ЛС продавца",
                        callback_data=f"chat_{product['seller_id']}"
                    )
                ]
            ]
        )

        await message.answer(
            f"📦 Лот #{product['id']}\n\n"
            f"📂 Категория: {product['category']}\n"
            f"👤 Продавец: {product['seller_name']}\n"
            f"📝 Описание: {product['description']}\n"
            f"💳 Оплата: {product['method']}\n"
            f"🏛️ Банк: {product['bank']}"
            f"{reviews_text}",
            reply_markup=keyboard
        )

@dp.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])

    product = next(
        (p for p in PRODUCTS if p["id"] == product_id),
        None
    )

    if not product:
        await callback.answer(
            "❌ Товар не найден",
            show_alert=True
        )
        return

    order_id = random.randint(100000, 999999)

    ORDERS[order_id] = {
        "buyer_id": callback.from_user.id,
        "seller_id": product["seller_id"],
        "product_id": product_id
    }

    await state.update_data(
        order_id=order_id,
        seller_id=product["seller_id"]
    )

    await state.set_state(OrderState.screenshot)

    await callback.message.answer(
        f"🧾 Заказ #{order_id}\n\n"
        f"💳 Способ: {product['method']}\n"
        f"🏛️ Банк: {product['bank']}\n"
        f"💰 Реквизиты: {product['details']}\n\n"
        f"📸 Отправьте чек после оплаты"
    )

    await callback.answer()

@dp.message(OrderState.screenshot, F.photo)
async def order_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()

    buyer = USERS.get(
        message.from_user.id,
        {"username": "Покупатель"}
    )

    await bot.send_message(
        data["seller_id"],
        f"🔔 Новый заказ #{data['order_id']}\n\n"
        f"👤 Покупатель: {buyer['username']}\n"
        f"💬 Напишите ему через раздел сообщений"
    )

    await bot.send_photo(
        data["seller_id"],
        message.photo[-1].file_id
    )

    chat_id = f"{message.from_user.id}_{data['seller_id']}"

    if chat_id not in MESSAGES:
        MESSAGES[chat_id] = []

    MESSAGES[chat_id].append(
        f"🛒 Создан заказ #{data['order_id']}"
    )

    await message.answer(
        "✅ Чек отправлен продавцу",
        reply_markup=main_keyboard()
    )

    await state.clear()

@dp.callback_query(F.data.startswith("chat_"))
async def open_chat(callback: CallbackQuery, state: FSMContext):
    seller_id = int(callback.data.split("_")[1])

    await state.update_data(chat_user=seller_id)

    await state.set_state(ChatState.waiting_message)

    await callback.message.answer(
        "💬 Напишите сообщение продавцу"
    )

    await callback.answer()

@dp.message(ChatState.waiting_message)
async def send_chat_message(message: Message, state: FSMContext):
    data = await state.get_data()

    receiver_id = data["chat_user"]

    sender = USERS.get(
        message.from_user.id,
        {"username": "Пользователь"}
    )

    chat_id = f"{message.from_user.id}_{receiver_id}"

    if chat_id not in MESSAGES:
        MESSAGES[chat_id] = []

    MESSAGES[chat_id].append(
        f"👤 {sender['username']}: {message.text}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Ответить",
                    callback_data=f"reply_{message.from_user.id}"
                )
            ]
        ]
    )

    try:
        await bot.send_message(
            receiver_id,
            f"💬 Новое сообщение\n\n"
            f"👤 {sender['username']}:\n"
            f"{message.text}",
            reply_markup=keyboard
        )
    except:
        pass

    await message.answer(
        "✅ Сообщение отправлено",
        reply_markup=main_keyboard()
    )

    await state.clear()

@dp.callback_query(F.data.startswith("reply_"))
async def reply_message(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])

    await state.update_data(chat_user=user_id)

    await state.set_state(ChatState.waiting_message)

    await callback.message.answer(
        "💬 Напишите ответ"
    )

    await callback.answer()

@dp.message(F.text == "💬 Сообщения")
async def messages_list(message: Message):
    found = False

    for chat_id, msgs in MESSAGES.items():

        ids = chat_id.split("_")

        if str(message.from_user.id) in ids:

            found = True

            await message.answer(
                "💬 История сообщений\n\n"
                + "\n".join(msgs[-10:])
            )

    if not found:
        await message.answer(
            "📭 Сообщений пока нет"
        )

@dp.callback_query(F.data.startswith("review_"))
async def review_start(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])

    await state.update_data(product_id=product_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐ 1",
                    callback_data="rate_1"
                ),
                InlineKeyboardButton(
                    text="⭐⭐⭐⭐⭐ 5",
                    callback_data="rate_5"
                )
            ]
        ]
    )

    await callback.message.answer(
        "🌟 Выберите оценку"
    )

    await callback.message.answer(
        "Оцените товар",
        reply_markup=keyboard
    )

    await callback.answer()

@dp.callback_query(F.data.startswith("rate_"))
async def review_rate(callback: CallbackQuery, state: FSMContext):
    stars = "⭐" if callback.data == "rate_1" else "⭐⭐⭐⭐⭐"

    await state.update_data(stars=stars)

    await state.set_state(ReviewState.comment)

    await callback.message.answer(
        "✍️ Напишите отзыв"
    )

    await callback.answer()

@dp.message(ReviewState.comment)
async def review_comment(message: Message, state: FSMContext):
    data = await state.get_data()

    for product in PRODUCTS:
        if product["id"] == data["product_id"]:

            username = USERS.get(
                message.from_user.id,
                {"username": "Пользователь"}
            )["username"]

            product["reviews"].append(
                f"👤 {username}: {data['stars']} — {message.text}"
            )

    await state.clear()

    await message.answer(
        "✅ Отзыв добавлен",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "⬅️ Назад")
async def back(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "🏠 Главное меню",
        reply_markup=main_keyboard()
    )

async def main():
    print("🚀 Sea Pay запущен")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())