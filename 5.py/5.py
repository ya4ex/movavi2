import asyncio
import logging
import random
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery, 
    FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = "8124381179:AAEX5dZEXWfQ3y5lR-ECQBY9QhDH9CXFZQ0"

# Картинки интерфейса
IMG = {
    "main": "Главое меню.png.png", 
    "catalog": "Каталог.png.png", 
    "auction": "Аукцон.png.png", 
    "exchange": "Обмен.png",       
    "profile": "Профиль.png.png", 
    "stats": "Статистика.png.png", 
    "msg": "Сообщения.png.png",    
    "about": "О сервисе.png.png", 
    "donate": "Донат.png.png"
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Локальная база данных в оперативной памяти (RAM)
USERS = {}        # Пользователи: ID -> {логин, пароль}
PRODUCTS = []     # Массив товаров в магазине
AUCTIONS = []     # Массив активных аукционов
EXCHANGES = []    # Массив объявлений обмена
ORDERS = {}       # База P2P сделок
GLOBAL_CHAT_MESSAGES = []  # Последние 15 сообщений общего чата

# Машины состояний (FSM) для пошагового ввода данных
class Registration(StatesGroup):
    username = State()
    password = State()

class Authorization(StatesGroup):
    username = State()
    password = State()

class ProductCreate(StatesGroup):
    category = State()
    description = State()
    photo = State()
    quantity = State()
    price = State()
    method = State()
    bank = State()
    details = State()

class AuctionCreate(StatesGroup):
    title = State()
    description = State()
    photo = State()
    min_bet = State()

class AuctionBid(StatesGroup):
    bid_amount = State()

class ExchangeCreate(StatesGroup):
    give_item = State()
    get_item = State()
    photo = State()       

class OrderState(StatesGroup):
    quantity = State()
    screenshot = State()

class ChatState(StatesGroup):
    waiting_message = State()

class GlobalChatState(StatesGroup):
    waiting_global_msg = State()

# Универсальный сборщик клавиатур (Reply и Inline)
def make_keyboard(buttons, is_inline=False):
    if is_inline:
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    keyboard_lines = []
    for row in buttons:
        line = []
        for btn in row:
            line.append(KeyboardButton(text=btn))
        keyboard_lines.append(line)
        
    return ReplyKeyboardMarkup(keyboard=keyboard_lines, resize_keyboard=True)

# Главная нижняя клавиатура (Reply)
def get_main_reply_keyboard():
    return make_keyboard([
        ["🛍️ Каталог", "🔨 Аукционы", "🔄 Обмен"], 
        ["➕ Продать", "🎯 Создать аукцион"],
        ["📂 Мои товары", "👤 Профиль"],
        ["💬 Общий чат", "📊 Статистика"], 
        ["❤️ Донат", "ℹ️ О сервисе"]
    ])

# Главное меню под сообщениями (Inline)
def get_main_inline_keyboard():
    kb = InlineKeyboardBuilder()
    items = [
        ("🛍️ Каталог", "open_catalog"), ("🔨 Аукционы", "open_auctions"), ("🔄 Обмен", "open_exchange"),
        ("➕ Продать", "open_sell"), ("🎯 Аукцион+", "open_create_auction"), ("📂 Мои лоты", "open_my_items"),
        ("👤 Профиль", "open_profile"), ("💬 Чат", "open_chat"), ("📊 Статы", "open_stats"),
        ("❤️ Донат", "open_donate"), ("ℹ️ Инфо", "open_info")
    ]
    for text, call_data in items:
        kb.button(text=text, callback_data=call_data)
    kb.adjust(3, 2, 2, 2, 2)
    return kb.as_markup()

# Кнопка возврата в меню для подразделов
def get_section_keyboard(extra_buttons=None):
    kb = InlineKeyboardBuilder()
    kb.button(text="📱 Главное меню", callback_data="go_to_main_menu")
    kb.adjust(1)
    
    if extra_buttons:
        for row in extra_buttons:
            for btn in row:
                kb.add(btn)
        
        layout = [1]
        for row in extra_buttons:
            layout.append(len(row))
        kb.adjust(*layout)
        
    return kb.as_markup()

# Движок отрисовки разделов. Удаляет старое сообщение и шлет картинку
async def send_section(event_source, img_key: str, text: str, section_buttons=None, is_root=False):
    img_path = IMG.get(img_key, "")
    is_callback = isinstance(event_source, CallbackQuery)
    message = event_source.message if is_callback else event_source
    
    ui_markup = get_main_inline_keyboard() if is_root else get_section_keyboard(section_buttons)

    if is_callback:
        try:
            await message.delete()  # Чистим историю чата для бесшовности (UX)
        except Exception:
            pass

    if img_path and os.path.exists(img_path):
        await message.answer_photo(
            photo=FSInputFile(img_path), 
            caption=text, 
            reply_markup=ui_markup, 
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            text=f"🖼️ (Файл {img_path} не найден)\n\n{text}", 
            reply_markup=ui_markup, 
            parse_mode="Markdown"
        )
        
    if is_callback:
        await event_source.answer()

# Переход в главное меню и обновление нижней панели
async def send_main_menu(event_source, text="🏠 Добро пожаловать в главное меню Sea Pay!"):
    if isinstance(event_source, Message):
        await event_source.answer(text="🏠 Переходим в меню...", reply_markup=get_main_reply_keyboard())
    await send_section(event_source, "main", text, is_root=True)

# Коллбеки для обработки кликов по инлайн-меню
@dp.callback_query(F.data == "go_to_main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_main_menu(call)

@dp.callback_query(F.data == "open_catalog")
async def cb_catalog(call: CallbackQuery): 
    await catalog(call.message)

@dp.callback_query(F.data == "open_auctions")
async def cb_auctions(call: CallbackQuery): 
    await list_auctions(call.message)

@dp.callback_query(F.data == "open_exchange")
async def cb_exchange(call: CallbackQuery): 
    await list_exchanges(call.message)

@dp.callback_query(F.data == "open_sell")
async def cb_sell(call: CallbackQuery, state: FSMContext): 
    await prod_start(call.message, state)

@dp.callback_query(F.data == "open_create_auction")
async def cb_create_auc(call: CallbackQuery, state: FSMContext): 
    await aud_start(call.message, state)

@dp.callback_query(F.data == "open_my_items")
async def cb_my_items(call: CallbackQuery): 
    await my_p(call.message)

@dp.callback_query(F.data == "open_profile")
async def cb_profile(call: CallbackQuery): 
    await profile(call.message)

@dp.callback_query(F.data == "open_chat")
async def cb_chat(call: CallbackQuery): 
    await open_global_chat(call.message)

@dp.callback_query(F.data == "open_stats")
async def cb_stats(call: CallbackQuery): 
    await stats(call.message)

@dp.callback_query(F.data == "open_donate")
async def cb_donate(call: CallbackQuery): 
    await donate(call.message)

@dp.callback_query(F.data == "open_info")
async def cb_info(call: CallbackQuery): 
    await about(call.message)

# Стартовая команда
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        text="🌊 Sea Pay — Маркетплейс игровых товаров", 
        reply_markup=make_keyboard([["🔐 Регистрация", "🔑 Авторизация"]])
    )

# Процесс регистрации (FSM)
@dp.message(F.text == "🔐 Регистрация")
async def reg_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Registration.username)
    await message.answer("📝 Введите логин (должен содержать ровно 7 английских букв):")

# Валидация логина (ровно 7 букв)
@dp.message(Registration.username)
async def reg_user(message: Message, state: FSMContext):
    u_input = message.text.strip()
    if len(u_input) != 7 or not u_input.isalpha(): 
        return await message.answer("❌ Ошибка: Логин должен состоять ровно из 7 букв!")
    await state.update_data(username=u_input)
    await state.set_state(Registration.password)
    await message.answer("🔑 Придумайте пароль (ровно 10 символов):")

# Валидация пароля (ровно 10 символов) и сохранение в USERS
@dp.message(Registration.password)
async def reg_pass(message: Message, state: FSMContext):
    p_input = message.text.strip()
    if len(p_input) != 10: 
        return await message.answer("❌ Ошибка: В пароле должно быть ровно 10 символов!")
    reg_data = await state.get_data()
    USERS[message.from_user.id] = {"username": reg_data["username"], "password": p_input}
    await state.clear()
    await send_main_menu(message, "✅ Регистрация успешно завершена!")

# Процесс авторизации (FSM)
@dp.message(F.text == "🔑 Авторизация")
async def auth_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Authorization.username)
    await message.answer("📝 Введите ваш логин:")

@dp.message(Authorization.username)
async def auth_user(message: Message, state: FSMContext):
    await state.update_data(username=message.text.strip())
    await state.set_state(Authorization.password)
    await message.answer("🔑 Введите ваш пароль:")

# Проверка учетных данных в словаре USERS
@dp.message(Authorization.password)
async def auth_pass(message: Message, state: FSMContext):
    auth_data = await state.get_data()
    p_input = message.text.strip()
    
    found_id = None
    for uid, info in USERS.items():
        if info["username"] == auth_data["username"] and info["password"] == p_input:
            found_id = uid
            break
            
    if not found_id:
        await state.clear()
        return await message.answer(
            text="❌ Неверный логин или пароль.", 
            reply_markup=make_keyboard([["🔐 Регистрация", "🔑 Авторизация"]])
        )
        
    if found_id != message.from_user.id: 
        USERS[message.from_user.id] = USERS.pop(found_id)
        
    await state.clear()
    await send_main_menu(message, "✅ Вы успешно вошли в систему!")

@dp.message(F.text == "⬅️ Назад")
async def back_button(message: Message, state: FSMContext):
    await state.clear()
    await send_main_menu(message)

# Вывод витрины магазина (фильтр по quantity > 0)
@dp.message(F.text == "🛍️ Каталог")
async def catalog(message: Message):
    available = []
    for item in PRODUCTS:
        if item["quantity"] > 0:
            available.append(item)
            
    if not available: 
        return await send_section(message, "catalog", "📭 На витрине магазина пока пусто.")
        
    await send_section(message, "catalog", "🛍️ Список товаров в каталоге:")
    for p in available:
        cost_text = "🎁 ДАРОМ!" if p["price"] == 0 else f"{p['price']} руб. за 1 шт."
        
        action_row = [
            [InlineKeyboardButton(text="💳 Купить / Выбрать кол-во", callback_data=f"buy_{p['id']}")],
            [InlineKeyboardButton(text="💬 Чат с продавцом", callback_data=f"chat_{p['seller_id']}")]
        ]
        pay_details = "Не требуется (Бесплатно)" if p["price"] == 0 else f"{p['method']} ({p['bank']})"
        
        info_block = (
            f"📦 *Лот #{p['id']}*\n\n📂 Категория: {p['category']}\n👤 Продавец: {p['seller_name']}\n"
            f"📝 Описание: {p['description']}\n📊 В наличии: *{p['quantity']} шт.*\n💰 Цена: *{cost_text}*\n💳 Оплата: {pay_details}"
        )
        if p.get("photo"): 
            await message.answer_photo(photo=p["photo"], caption=info_block, reply_markup=InlineKeyboardMarkup(inline_keyboard=action_row), parse_mode="Markdown")
        else: 
            await message.answer(text=info_block, reply_markup=InlineKeyboardMarkup(inline_keyboard=action_row), parse_mode="Markdown")

# Добавление товара на продажу (FSM)
@dp.message(F.text == "➕ Продать")
async def prod_start(message: Message, state: FSMContext):
    if message.from_user.id not in USERS: 
        return await message.answer("❌ Пожалуйста, сначала авторизуйтесь.")
    await state.set_state(ProductCreate.category)
    await message.answer(text="📂 Выберите категорию вашего товара:", reply_markup=make_keyboard([["📱 Telegram", "🎮 Игры"], ["🔄 Объявление обмена"], ["⬅️ Назад"]]))

@dp.message(ProductCreate.category)
async def prod_cat(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад": 
        await state.clear()
        return await send_main_menu(message)
    if message.text == "🔄 Объявление обмена": 
        await state.set_state(ExchangeCreate.give_item)
        return await message.answer("🔄 Что вы хотите отдать для обмена?:")
    await state.update_data(category=message.text)
    await state.set_state(ProductCreate.description)
    await message.answer("📝 Напишите описание вашего товара:")

@dp.message(ProductCreate.description)
async def prod_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(ProductCreate.photo) 
    await message.answer(text="📸 Отправьте фото товара:", reply_markup=make_keyboard([["⏩ Пропустить фото"], ["⬅️ Назад"]]))

@dp.message(ProductCreate.photo, F.photo)
async def prod_photo_get(message: Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await state.set_state(ProductCreate.quantity)
    await message.answer("📊 Укажите количество товара в наличии:", reply_markup=make_keyboard([["⬅️ Назад"]]))

@dp.message(ProductCreate.photo, F.text == "⏩ Пропустить фото")
async def prod_photo_skip(message: Message, state: FSMContext):
    await state.update_data(photo=None) 
    await state.set_state(ProductCreate.quantity)
    await message.answer("📊 Укажите количество товара в наличии:", reply_markup=make_keyboard([["⬅️ Назад"]]))

@dp.message(ProductCreate.quantity)
async def prod_qty_get(message: Message, state: FSMContext):
    try: 
        qty = int(message.text.strip())
    except ValueError: 
        return await message.answer("❌ Введите целое число!")
    if qty <= 0: 
        return await message.answer("❌ Количество должно быть больше нуля!")
    await state.update_data(quantity=qty)
    await state.set_state(ProductCreate.price)
    await message.answer("💰 Укажите стоимость за 1 штуку (0 = ДАРОМ):")

@dp.message(ProductCreate.price)
async def prod_price(message: Message, state: FSMContext):
    try: 
        val = int(message.text.strip())
    except ValueError: 
        return await message.answer("❌ Введите корректное число!")
    if val < 0 or val > 100000: 
        return await message.answer("❌ Сумма от 0 до 100 000 рублей!")
    await state.update_data(price=val)
    fsm_data = await state.get_data()
    
    if val == 0:
        PRODUCTS.append({"id": len(PRODUCTS) + 1, "seller_id": message.from_user.id, "seller_name": USERS[message.from_user.id]["username"], "category": fsm_data["category"], "description": fsm_data["description"], "photo": fsm_data["photo"], "quantity": fsm_data["quantity"], "price": 0, "method": "-", "bank": "-", "details": "-"})
        await state.clear()
        return await send_main_menu(message, f"✅ Товар успешно добавлен [ДАРОМ] в количестве {fsm_data['quantity']} шт.!")
        
    await state.set_state(ProductCreate.method)
    await message.answer(text="💳 Выберите тип оплаты:", reply_markup=make_keyboard([["📲 СБП"], ["💳 Карта"], ["⬅️ Назад"]]))

@dp.message(ProductCreate.method)
async def prod_meth(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад": 
        await state.clear()
        return await send_main_menu(message)
    await state.update_data(method=message.text)
    await state.set_state(ProductCreate.bank)
    await message.answer(text="🏛️ Выберите ваш банк:", reply_markup=make_keyboard([["🟩 Сбербанк", "🟨 Т-Банк"], ["🟦 ВТБ", "🟥 Альфа-Банк"], ["🏛️ Другой"], ["⬅️ Назад"]]))

@dp.message(ProductCreate.bank)
async def prod_bank(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад": 
        await state.clear()
        return await send_main_menu(message)
    await state.update_data(bank=message.text)
    await state.set_state(ProductCreate.details)
    await message.answer("💳 Введите ваши реквизиты:")

@dp.message(ProductCreate.details)
async def prod_fin(message: Message, state: FSMContext):
    fsm_data = await state.get_data()
    PRODUCTS.append({"id": len(PRODUCTS) + 1, "seller_id": message.from_user.id, "seller_name": USERS[message.from_user.id]["username"], "category": fsm_data["category"], "description": fsm_data["description"], "photo": fsm_data["photo"], "quantity": fsm_data["quantity"], "price": fsm_data["price"], "method": fsm_data["method"], "bank": fsm_data["bank"], "details": message.text})
    await state.clear()
    await send_main_menu(message, f"✅ Товар успешно добавлен! Количество: {fsm_data['quantity']} шт.")

# Создание объявления обмена (Бартер)
@dp.message(ExchangeCreate.give_item)
async def exchange_give(message: Message, state: FSMContext):
    await state.update_data(give_item=message.text)
    await state.set_state(ExchangeCreate.get_item)
    await message.answer("🎯 Что бы вы хотели получить взамен?:")

@dp.message(ExchangeCreate.get_item)
async def exchange_get(message: Message, state: FSMContext):
    await state.update_data(get_item=message.text)
    await state.set_state(ExchangeCreate.photo) 
    await message.answer(text="📸 Отправьте фото предмета или пропустите:", reply_markup=make_keyboard([["⏩ Пропустить фото"], ["⬅️ Назад"]]))

@dp.message(ExchangeCreate.photo, F.photo)
async def exchange_photo_get(message: Message, state: FSMContext):
    fsm_data = await state.get_data()
    EXCHANGES.append({"id": len(EXCHANGES) + 1, "seller_id": message.from_user.id, "seller_name": USERS[message.from_user.id]["username"], "give": fsm_data["give_item"], "get": fsm_data["get_item"], "photo": message.photo[-1].file_id})
    await state.clear()
    await send_main_menu(message, "✅ Объявление об обмене опубликовано!")

@dp.message(ExchangeCreate.photo, F.text == "⏩ Пропустить фото")
async def exchange_photo_skip(message: Message, state: FSMContext):
    fsm_data = await state.get_data()
    EXCHANGES.append({"id": len(EXCHANGES) + 1, "seller_id": message.from_user.id, "seller_name": USERS[message.from_user.id]["username"], "give": fsm_data["give_item"], "get": fsm_data["get_item"], "photo": None})
    await state.clear()
    await send_main_menu(message, "✅ Объявление об обмене опубликовано!")

# Просмотр ленты обменов
@dp.message(F.text == "🔄 Обмен")
async def list_exchanges(message: Message):
    if not EXCHANGES: 
        return await send_section(message, "exchange", "📭 Объявлений об обмене пока нет.")
    await send_section(message, "exchange", "🔄 Список активных предложений обмена:")
    for ex in EXCHANGES:
        ex_btns = [[InlineKeyboardButton(text="🙋 Отозваться", callback_data=f"respond_{ex['id']}"), InlineKeyboardButton(text="💬 ЛС продавца", callback_data=f"chat_{ex['seller_id']}")]]
        text = f"🔄 *Объявление об обмене #{ex['id']}*\n\n👤 Автор: {ex['seller_name']}\n📤 Отдаёт: {ex['give']}\n📥 Хочет: {ex['get']}"
        if ex.get("photo"): 
            await message.answer_photo(photo=ex["photo"], caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=ex_btns), parse_mode="Markdown")
        else: 
            await message.answer(text=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=ex_btns), parse_mode="Markdown")

# Отклик на обмен (Уведомление автора лота)
@dp.callback_query(F.data.startswith("respond_"))
async def respond_exchange(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    ex = None
    for x in EXCHANGES:
        if x["id"] == target_id:
            ex = x
            break
            
    if not ex: 
        return await callback.answer("❌ Объявление не найдено!", show_alert=True)
    try: 
        await bot.send_message(ex["seller_id"], f"🔔 На ваше объявление об обмене #{ex['id']} откликнулся пользователь!")
    except Exception: 
        pass
    await callback.answer("✅ Автор объявления уведомлен!", show_alert=True)

# Работа с общим чатом
@dp.message(F.text == "💬 Общий чат")
async def open_global_chat(message: Message):
    chat_action_btns = [[InlineKeyboardButton(text="✍️ Написать сообщение", callback_data="chat_write_global"), InlineKeyboardButton(text="🔄 Обновить чат", callback_data="chat_refresh_global")]]
    await send_section(message, "msg", build_chat_text(), section_buttons=chat_action_btns)

@dp.callback_query(F.data == "chat_refresh_global")
async def refresh_global_chat(callback: CallbackQuery):
    chat_action_btns = [[InlineKeyboardButton(text="✍️ Написать сообщение", callback_data="chat_write_global"), InlineKeyboardButton(text="🔄 Обновить чат", callback_data="chat_refresh_global")]]
    final_kb = get_section_keyboard(chat_action_btns)
    try: 
        await callback.message.edit_caption(caption=build_chat_text(), reply_markup=final_kb, parse_mode="Markdown")
    except Exception: 
        pass
    await callback.answer("🔄 Чат обновлен!")

@dp.callback_query(F.data == "chat_write_global")
async def ask_global_msg(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in USERS: 
        return await callback.answer("❌ Сначала авторизуйтесь!", show_alert=True)
    await state.set_state(GlobalChatState.waiting_global_msg)
    await callback.message.answer("📝 Введите ваше сообщение для общего чата:")
    await callback.answer()

# Сохранение лога чата (лимит 15 строк)
@dp.message(GlobalChatState.waiting_global_msg)
async def save_global_msg(message: Message, state: FSMContext):
    username = USERS.get(message.from_user.id)["username"]
    GLOBAL_CHAT_MESSAGES.append({"user": username, "text": message.text, "time": datetime.now().strftime("%H:%M")})
    if len(GLOBAL_CHAT_MESSAGES) > 15: 
        GLOBAL_CHAT_MESSAGES.pop(0)
    await state.clear()
    await open_global_chat(message)

# Покупка товара (P2P сделка)
@dp.callback_query(F.data.startswith("buy_"))
async def buy_qty_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in USERS: 
        return await callback.answer("❌ Вы не авторизованы!", show_alert=True)
        
    t_id = int(callback.data.split("_")[1])
    p = None
    for x in PRODUCTS:
        if x["id"] == t_id:
            p = x
            break
            
    if not p or p["quantity"] <= 0: 
        return await callback.answer("❌ Товар закончился!", show_alert=True)
    
    await state.update_data(buy_prod_id=p["id"])
    await state.set_state(OrderState.quantity) 
    await callback.message.answer(f"📊 Товар: *{p['description']}*\n💰 Цена: {p['price']} руб./шт\n📈 На складе: {p['quantity']} шт.\n\n✏️ *Введите количество штук для покупки:*", parse_mode="Markdown")
    await callback.answer()

@dp.message(OrderState.quantity)
async def buy_qty_get(message: Message, state: FSMContext):
    try: 
        req_qty = int(message.text.strip())
    except ValueError: 
        return await message.answer("❌ Введите количество цифрами!")
    if req_qty <= 0: 
        return await message.answer("❌ Количество должно быть больше 0!")
    
    fsm_data = await state.get_data()
    p = None
    for x in PRODUCTS:
        if x["id"] == fsm_data["buy_prod_id"]:
            p = x
            break
            
    if not p: 
        await state.clear()
        return await message.answer("❌ Товар не найден.")
    if req_qty > p["quantity"]: 
        return await message.answer(f"❌ Доступно максимум: {p['quantity']} шт.")
        
    total_price = p["price"] * req_qty
    order_id = random.randint(100000, 999999)
    await state.update_data(order_id=order_id, seller_id=p["seller_id"], final_qty=req_qty, total_sum=total_price)
    
    ORDERS[order_id] = {"buyer_id": message.from_user.id, "buyer_name": USERS[message.from_user.id]["username"], "seller_id": p["seller_id"], "qty": req_qty, "total": total_price, "prod_desc": p["description"]}
    
    if total_price == 0:  # Логика бесплатной раздачи
        p["quantity"] -= req_qty
        try: 
            await bot.send_message(p["seller_id"], f"🎁 *Бесплатный заказ #{order_id}!*\nПокупатель @{USERS[message.from_user.id]['username']} забрал {req_qty} шт.", parse_mode="Markdown")
        except Exception: 
            pass
        await state.clear()
        go_pm = [[InlineKeyboardButton(text="💬 Перейти в ЛС к продавцу", callback_data=f"chat_{p['seller_id']}")]]
        return await message.answer(f"🎁 Заказ #{order_id} оформлен бесплатно! ({req_qty} шт.)", reply_markup=InlineKeyboardMarkup(inline_keyboard=go_pm))

    await state.set_state(OrderState.screenshot)
    await message.answer(text=f"🧾 *Заказ #{order_id}*\n💰 К оплате: *{total_price} руб.* ({req_qty} шт.)\n🏛️ Банк: {p['bank']}\n💳 Реквизиты: `{p['details']}`\n\nПереведите сумму и отправьте скриншот чека:", parse_mode="Markdown")

# Фиксация чека оплаты и пересылка продавцу в ЛС
@dp.message(OrderState.screenshot, F.photo)
async def buy_screenshot_get(message: Message, state: FSMContext):
    fsm_data = await state.get_data()
    o_id = fsm_data["order_id"]
    s_id = fsm_data["seller_id"]
    qty = fsm_data["final_qty"]
    total = fsm_data["total_sum"]
    
    p = None
    for x in PRODUCTS:
        if x["id"] == fsm_data["buy_prod_id"]:
            p = x
            break
            
    if p: 
        p["quantity"] -= qty  # Списание со склада

    try:
        seller_text = f"🔔 *Новый заказ #{o_id}!*\n👤 Покупатель: {USERS[message.from_user.id]['username']}\n📦 Кол-во: *{qty} шт.*\n💰 Сумма: *{total} руб.*\n\nЧек ниже 👇"
        await bot.send_message(s_id, text=seller_text, parse_mode="Markdown")
        await bot.send_photo(s_id, message.photo[-1].file_id)
    except Exception: 
        pass
        
    await state.clear()
    pm_keyboard = [[InlineKeyboardButton(text="💬 Перейти в ЛС к продавцу", callback_data=f"chat_{s_id}")]]
    await message.answer(text=f"✅ Чек отправлен продавцу!\n🧾 Номер заказа: `#{o_id}`.\n\nСвяжитесь с продавцом для завершения сделки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=pm_keyboard), parse_mode="Markdown")

# Создание аукциона (FSM)
@dp.message(F.text == "🎯 Создать аукцион")
async def aud_start(message: Message, state: FSMContext):
    if message.from_user.id not in USERS: 
        return await message.answer("❌ Сначала авторизуйтесь!")
    await state.set_state(AuctionCreate.title)
    await message.answer("🔨 Введите название лота:")

@dp.message(AuctionCreate.title)
async def aud_t(message: Message, state: FSMContext): 
    await state.update_data(title=message.text)
    await state.set_state(AuctionCreate.description)
    await message.answer("📝 Введите описание:")

@dp.message(AuctionCreate.description)
async def aud_d(message: Message, state: FSMContext): 
    await state.update_data(description=message.text)
    await state.set_state(AuctionCreate.photo)
    await message.answer("📸 Отправьте фото:")

@dp.message(AuctionCreate.photo, F.photo)
async def aud_p(message: Message, state: FSMContext): 
    await state.update_data(photo=message.photo[-1].file_id)
    await state.set_state(AuctionCreate.min_bet)
    await message.answer("💰 Введите начальную цену:")

@dp.message(AuctionCreate.min_bet)
async def aud_f(message: Message, state: FSMContext):
    try: 
        min_bet = int(message.text)
    except ValueError: 
        return await message.answer("❌ Введите число!")
    fsm_data = await state.get_data()
    # Срок жизни лота - строго 20 минут
    AUCTIONS.append({"id": len(AUCTIONS) + 1, "seller_id": message.from_user.id, "seller_name": USERS[message.from_user.id]["username"], "title": fsm_data["title"], "description": fsm_data["description"], "photo": fsm_data["photo"], "current_price": min_bet, "last_bidder": "Ставок нет", "end_time": datetime.now() + timedelta(minutes=20)})
    await state.clear()
    await send_main_menu(message, "✅ Лот выставлен на торги!")

# Вывод ленты торгов (фильтр по дедлайну времени)
@dp.message(F.text == "🔨 Аукционы")
async def list_auctions(message: Message):
    now = datetime.now()
    active_items = []
    for a in AUCTIONS:
        if a["end_time"] > now:
            active_items.append(a)
            
    if not active_items: 
        return await send_section(message, "auction", "📭 Активных аукционов нет.")
    
    await send_section(message, "auction", "🔨 Актуальные лоты на аукционе:")
    for auc in active_items:
        delta_time = auc["end_time"] - now
        mins, secs = divmod(int(delta_time.total_seconds()), 60)
        
        auc_btns = [[InlineKeyboardButton(text="💵 Сделать ставку", callback_data=f"bid_{auc['id']}")]]
        # Тайм-лок: ЛС с продавцом доступно только если осталось < 5 минут
        if delta_time.total_seconds() <= 300: 
            auc_btns.append([InlineKeyboardButton(text="💬 Чат с продавцом", callback_data=f"chat_{auc['seller_id']}")])
        else: 
            auc_btns.append([InlineKeyboardButton(text="🔒 Чат (осталось < 5 мин)", callback_data="ls_locked")])
        
        text = f"🔨 *Лот #{auc['id']}: {auc['title']}*\n\n📝 Описание: {auc['description']}\n👤 Продавец: {auc['seller_name']}\n💰 Ставка: {auc['current_price']} руб.\n👑 Лидер: {auc['last_bidder']}\n\n⏳ Осталось: {mins} мин. {secs} сек."
        await message.answer_photo(photo=auc["photo"], caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=auc_btns), parse_mode="Markdown")

@dp.callback_query(F.data == "ls_locked")
async def ls_lock(callback: CallbackQuery): 
    await callback.answer("🔒 Чат откроется, когда останется меньше 5 минут!", show_alert=True)

# Повышение ставки на аукционе
@dp.callback_query(F.data.startswith("bid_"))
async def bid_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in USERS: 
        return await callback.answer("❌ Вы не авторизованы!", show_alert=True)
        
    a_id = int(callback.data.split("_")[1])
    auc = None
    for x in AUCTIONS:
        if x["id"] == a_id:
            auc = x
            break
            
    if not auc or auc["end_time"] < datetime.now(): 
        return await callback.answer("❌ Торги завершены!", show_alert=True)
    
    await state.update_data(auc_id=auc["id"])
    await state.set_state(AuctionBid.bid_amount)
    await callback.message.answer(f"📈 Текущая цена: {auc['current_price']} руб.\nВведите вашу ставку:")
    await callback.answer()

# Проверка, чтобы новая ставка была выше текущей
@dp.message(AuctionBid.bid_amount)
async def bid_finish(message: Message, state: FSMContext):
    try: 
        bid = int(message.text)
    except ValueError: 
        return await message.answer("❌ Введите число!")
    fsm_data = await state.get_data()
    
    auc = None
    for x in AUCTIONS:
        if x["id"] == fsm_data["auc_id"]:
            auc = x
            break
            
    if not auc or auc["end_time"] < datetime.now(): 
        return await message.answer("❌ Аукцион закрылся!")
    if bid <= auc["current_price"]: 
        return await message.answer("❌ Ставка должна быть выше текущей!")
    
    auc["current_price"] = bid
    auc["last_bidder"] = USERS[message.from_user.id]["username"]
    await state.clear()
    await send_main_menu(message, "✅ Ваша ставка принята!")

# ЛС-система (Peer-to-Peer отправка сообщений внутри бота)
@dp.callback_query(F.data.startswith("chat_"))
async def chat_st(callback: CallbackQuery, state: FSMContext):
    await state.update_data(chat_user=int(callback.data.split("_")[1].strip()))
    await state.set_state(ChatState.waiting_message)
    await send_section(callback, "msg", "💬 *Окно личных сообщений*\n\nНапишите текст вашего сообщения продавцу ниже:")

@dp.message(ChatState.waiting_message)
async def chat_snd(message: Message, state: FSMContext):
    fsm_data = await state.get_data()
    sender = USERS.get(message.from_user.id, {"username": "Аноним"})
    try:
        reply_btns = [[InlineKeyboardButton(text="💬 Ответить", callback_data=f"chat_{message.from_user.id}")]]
        await bot.send_message(chat_id=fsm_data["chat_user"], text=f"💬 (ЛС) От пользователя {sender['username']}:\n{message.text}", reply_markup=InlineKeyboardMarkup(inline_keyboard=reply_btns))
    except Exception: 
        pass
    await state.clear()
    await send_main_menu(message, "✅ Личное сообщение доставлено!")

# Панель управления своими лотами
@dp.message(F.text == "📂 Мои товары")
async def my_p(message: Message):
    mine_prod = [p for p in PRODUCTS if p["seller_id"] == message.from_user.id]
    mine_exch = [e for e in EXCHANGES if e["seller_id"] == message.from_user.id]
    
    if not mine_prod and not mine_exch: 
        return await message.answer("📭 У вас нет active лотов.")
        
    for p in mine_prod:
        btn = [[InlineKeyboardButton(text="🗑️ Снять с продажи", callback_data=f"del_{p['id']}")]]; 
        await message.answer(text=f"📦 *Товар #{p['id']}*\n📝 {p['description']}\n📊 Остаток: {p['quantity']} шт.", reply_markup=InlineKeyboardMarkup(inline_keyboard=btn), parse_mode="Markdown")
        
    for e in mine_exch:
        btn = [[InlineKeyboardButton(text="🗑️ Удалить обмен", callback_data=f"delex_{e['id']}")]]; 
        await message.answer(text=f"🔄 *Обмен #{e['id']}*\n📝 {e['give']} -> {e['get']}", reply_markup=InlineKeyboardMarkup(inline_keyboard=btn), parse_mode="Markdown")

# Удаление лотов из ОЗУ
@dp.callback_query(F.data.startswith("del_"))
async def del_p(callback: CallbackQuery):
    t_id = int(callback.data.split("_")[1])
    for x in PRODUCTS:
        if x["id"] == t_id and x["seller_id"] == callback.from_user.id:
            PRODUCTS.remove(x)
            break
    await callback.message.edit_text("🗑️ Товар удален.")

@dp.callback_query(F.data.startswith("delex_"))
async def del_ex(callback: CallbackQuery):
    e_id = int(callback.data.split("_")[1])
    for x in EXCHANGES:
        if x["id"] == e_id and x["seller_id"] == callback.from_user.id:
            EXCHANGES.remove(x)
            break
    await callback.message.edit_text("🗑️ Обмен удален.")

# Профиль, статистика и информационные блоки
@dp.message(F.text == "👤 Профиль")
async def profile(message: Message):
    u = USERS.get(message.from_user.id)
    await send_section(message, "profile", f"👤 *Личный кабинет Sea Pay*\n\n🆔 Логин: {u['username'] if u else 'Не авторизован'}\n⭐ Рейтинг: 5.0 / 5.0")

@dp.message(F.text == "📊 Статистика")
async def stats(message: Message):
    await send_section(message, "stats", f"📊 *Статистика:*\n\n• Пользователей: {len(USERS)}\n• Товаров: {len(PRODUCTS)}\n• Обменов: {len(EXCHANGES)}\n• Аукционов: {len(AUCTIONS)}")

@dp.message(F.text == "ℹ️ О сервисе")
async def about(message: Message):
    await send_section(message, "about", "🌊 *Sea Pay* — Маркетплейс игровых товаров с поддержкой P2P сделок, раздач и аукционов.")

@dp.message(F.text == "❤️ Донат")
async def donate(message: Message):
    donate_btn = [[InlineKeyboardButton(text="💸 Поддержать автора", url="https://t.me/send?start=IVzGwn2pggSS")]]
    await send_section(message, "donate", "❤️ Спасибо за поддержку нашего проекта!", section_buttons=donate_btn)

# Генератор строки чата
def build_chat_text():
    if not GLOBAL_CHAT_MESSAGES: 
        return "💬 *Общий чат Sea Pay*\n\nЗдесь пока пусто."
    return "💬 *Общий чат (Последние 15):*\n\n" + "\n".join([f"⏱ `[{m['time']}]` *{m['user']}*: {m['text']}" for m in GLOBAL_CHAT_MESSAGES])

# Точка запуска асинхронного ядра бота
async def main():
    print("Бот успешно запущен и готов к работе.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())