import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
import database as db
from config import ADMIN_ID
from config import BOT_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ── STATES ──
class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    city = State()
    about = State()
    photo = State()

class EditProfile(StatesGroup):
    choose_field = State()
    name = State()
    age = State()
    city = State()
    about = State()
    photo = State()

# ── KEYBOARDS ──
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🌐 Лента"), KeyboardButton(text="🔥 Топ"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="❤️ Лайки"), KeyboardButton(text="💞 Мэтчи")],
        [KeyboardButton(text="⚙️ Настройки")]
    ], resize_keyboard=True)

def gender_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👦 Парень"), KeyboardButton(text="👧 Девушка")]
    ], resize_keyboard=True)

def profile_actions_kb(user_id, target_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️", callback_data=f"like:{target_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"dislike:{target_id}"),
        ],
        [InlineKeyboardButton(text="🚩 Пожаловаться", callback_data=f"report:{target_id}")]
    ])

def profile_edit_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Имя", callback_data="edit:name"),
         InlineKeyboardButton(text="🎂 Возраст", callback_data="edit:age")],
        [InlineKeyboardButton(text="🏙 Город", callback_data="edit:city"),
         InlineKeyboardButton(text="📝 О себе", callback_data="edit:about")],
        [InlineKeyboardButton(text="📸 Фото", callback_data="edit:photo")],
        [InlineKeyboardButton(text="🔴 Отключить анкету", callback_data="toggle_profile"),
         InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_profile")]
    ])

def match_kb(matched_username):
    kb = [[InlineKeyboardButton(text="💬 Написать", url=f"https://t.me/{matched_username}")]] if matched_username else []
    return InlineKeyboardMarkup(inline_keyboard=kb) if kb else None

# ── HELPERS ──
def gender_emoji(gender):
    return "👦" if gender == "male" else "👧"

async def send_profile_card(chat_id, user: dict, kb=None, extra_text=""):
    gender_e = gender_emoji(user['gender'])
    text = (
        f"{gender_e} <b>{user['name']}</b>, {user['age']}\n"
        f"🏙 {user['city']}\n\n"
        f"{user['about']}"
    )
    if extra_text:
        text = extra_text + "\n\n" + text
    if user.get('photo_id'):
        await bot.send_photo(chat_id, user['photo_id'], caption=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

# ── /START ──
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if user:
        await message.answer(
            f"👋 С возвращением, <b>{user['name']}</b>!\n\nИспользуй меню ниже 👇",
            reply_markup=main_menu()
        )
    else:
        await message.answer(
            "👋 Привет! Добро пожаловать в бот знакомств.\n\n"
            "Давай создадим твою анкету! Как тебя зовут?"
        )
        await state.set_state(Registration.name)

# ── REGISTRATION ──
@dp.message(Registration.name)
async def reg_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 30:
        await message.answer("❌ Имя должно быть от 2 до 30 символов. Попробуй ещё раз:")
        return
    await state.update_data(name=name)
    await message.answer(f"Отлично, <b>{name}</b>! Сколько тебе лет?")
    await state.set_state(Registration.age)

@dp.message(Registration.age)
async def reg_age(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (14 <= int(message.text) <= 60):
        await message.answer("❌ Введи возраст числом от 14 до 60:")
        return
    await state.update_data(age=int(message.text))
    await message.answer("Ты парень или девушка?", reply_markup=gender_kb())
    await state.set_state(Registration.gender)

@dp.message(Registration.gender, F.text.in_(["👦 Парень", "👧 Девушка"]))
async def reg_gender(message: Message, state: FSMContext):
    gender = "male" if message.text == "👦 Парень" else "female"
    await state.update_data(gender=gender)
    await message.answer("Из какого ты города?", reply_markup=ReplyKeyboardMarkup(keyboard=[[]], resize_keyboard=True))
    await message.answer("Напиши свой город:")
    await state.set_state(Registration.city)

@dp.message(Registration.city)
async def reg_city(message: Message, state: FSMContext):
    city = message.text.strip()
    if len(city) < 2:
        await message.answer("❌ Слишком короткое название. Попробуй ещё:")
        return
    await state.update_data(city=city)
    await message.answer("Расскажи немного о себе (до 200 символов):")
    await state.set_state(Registration.about)

@dp.message(Registration.about)
async def reg_about(message: Message, state: FSMContext):
    about = message.text.strip()
    if len(about) > 200:
        await message.answer("❌ Слишком длинно. Максимум 200 символов:")
        return
    await state.update_data(about=about)
    await message.answer("📸 Отправь своё фото (или напиши /skip чтобы пропустить):")
    await state.set_state(Registration.photo)

@dp.message(Registration.photo, F.photo)
async def reg_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await finish_registration(message, state)

@dp.message(Registration.photo, Command("skip"))
async def reg_photo_skip(message: Message, state: FSMContext):
    await state.update_data(photo_id=None)
    await finish_registration(message, state)

async def finish_registration(message: Message, state: FSMContext):
    data = await state.get_data()
    db.create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        name=data['name'],
        age=data['age'],
        gender=data['gender'],
        city=data['city'],
        about=data['about'],
        photo_id=data.get('photo_id')
    )
    await state.clear()
    await message.answer(
        f"✅ <b>Анкета создана!</b>\n\n"
        f"Добро пожаловать, <b>{data['name']}</b>! 🎉\n"
        f"Теперь ты можешь смотреть анкеты и знакомиться.",
        reply_markup=main_menu()
    )

# ── ЛЕНТА ──
@dp.message(F.text == "🌐 Лента")
async def show_feed(message: Message):
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала создай анкету — /start")
        return

    profiles = db.get_feed(message.from_user.id)
    if not profiles:
        await message.answer("😔 Анкеты закончились. Загляни позже!")
        return

    target = profiles[0]
    kb = profile_actions_kb(message.from_user.id, target['user_id'])
    await send_profile_card(message.chat.id, target, kb)

# ── ЛАЙК / ДИЗЛАЙК ──
@dp.callback_query(F.data.startswith("like:"))
async def handle_like(call: CallbackQuery):
    target_id = int(call.data.split(":")[1])
    liker = db.get_user(call.from_user.id)
    target = db.get_user(target_id)

    if not liker or not target:
        await call.answer("Анкета не найдена")
        return

    is_match = db.add_like(call.from_user.id, target_id)
    await call.answer("❤️")

    if is_match:
        # Уведомляем обоих
        liker_link = f"@{liker['username']}" if liker.get('username') else liker['name']
        target_link = f"@{target['username']}" if target.get('username') else target['name']

        await bot.send_message(
            call.from_user.id,
            f"💞 <b>Мэтч!</b>\nТы и <b>{target['name']}</b> понравились друг другу!",
            reply_markup=match_kb(target.get('username'))
        )
        await bot.send_message(
            target_id,
            f"💞 <b>Мэтч!</b>\nТы и <b>{liker['name']}</b> понравились друг другу!",
            reply_markup=match_kb(liker.get('username'))
        )
    else:
        # Уведомляем цель о лайке (анонимно)
        await bot.send_message(
            target_id,
            f"❤️ Кто-то поставил тебе лайк! Зайди в раздел <b>Лайки</b> чтобы узнать кто."
        )

    # Показываем следующую анкету
    profiles = db.get_feed(call.from_user.id)
    if profiles:
        next_p = profiles[0]
        kb = profile_actions_kb(call.from_user.id, next_p['user_id'])
        await send_profile_card(call.message.chat.id, next_p, kb)
    else:
        await call.message.answer("😔 Анкеты закончились. Загляни позже!")

@dp.callback_query(F.data.startswith("dislike:"))
async def handle_dislike(call: CallbackQuery):
    target_id = int(call.data.split(":")[1])
    db.add_dislike(call.from_user.id, target_id)
    await call.answer("👎")

    profiles = db.get_feed(call.from_user.id)
    if profiles:
        next_p = profiles[0]
        kb = profile_actions_kb(call.from_user.id, next_p['user_id'])
        await send_profile_card(call.message.chat.id, next_p, kb)
    else:
        await call.message.answer("😔 Анкеты закончились. Загляни позже!")

# ── ЖАЛОБА ──
@dp.callback_query(F.data.startswith("report:"))
async def handle_report(call: CallbackQuery):
    target_id = int(call.data.split(":")[1])
    db.add_report(call.from_user.id, target_id)
    await call.answer("🚩 Жалоба отправлена", show_alert=True)

# ── ПРОФИЛЬ ──
@dp.message(F.text == "👤 Профиль")
async def show_profile(message: Message):
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала создай анкету — /start")
        return

    stats = db.get_user_stats(message.from_user.id)
    gender_e = gender_emoji(user['gender'])
    status = "🟢 Активна" if user['active'] else "🔴 Отключена"

    text = (
        f"{gender_e} <b>{user['name']}</b>, {user['age']}\n"
        f"🏙 {user['city']}\n\n"
        f"{user['about']}\n\n"
        f"❤️ {stats['likes_received']}   💞 {stats['matches']}   👁 {stats['views']}\n"
        f"Анкета: {status}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Редактировать профиль", callback_data="edit_profile")],
        [InlineKeyboardButton(text="🔴 Отключить анкету" if user['active'] else "🟢 Включить анкету", callback_data="toggle_profile")]
    ])

    if user.get('photo_id'):
        await message.answer_photo(user['photo_id'], caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)

# ── РЕДАКТИРОВАНИЕ ──
@dp.callback_query(F.data == "edit_profile")
async def edit_profile_menu(call: CallbackQuery):
    await call.message.answer("Что хочешь изменить?", reply_markup=profile_edit_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("edit:"))
async def edit_field(call: CallbackQuery, state: FSMContext):
    field = call.data.split(":")[1]
    prompts = {
        "name": ("✏️ Введи новое имя:", EditProfile.name),
        "age": ("🎂 Введи новый возраст:", EditProfile.age),
        "city": ("🏙 Введи новый город:", EditProfile.city),
        "about": ("📝 Напиши о себе (до 200 символов):", EditProfile.about),
        "photo": ("📸 Отправь новое фото:", EditProfile.photo),
    }
    prompt, state_obj = prompts[field]
    await call.message.answer(prompt)
    await state.set_state(state_obj)
    await call.answer()

@dp.message(EditProfile.name)
async def do_edit_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 30:
        await message.answer("❌ Имя от 2 до 30 символов:")
        return
    db.update_user(message.from_user.id, name=name)
    await state.clear()
    await message.answer("✅ Имя обновлено!", reply_markup=main_menu())

@dp.message(EditProfile.age)
async def do_edit_age(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (14 <= int(message.text) <= 60):
        await message.answer("❌ Возраст от 14 до 60:")
        return
    db.update_user(message.from_user.id, age=int(message.text))
    await state.clear()
    await message.answer("✅ Возраст обновлён!", reply_markup=main_menu())

@dp.message(EditProfile.city)
async def do_edit_city(message: Message, state: FSMContext):
    city = message.text.strip()
    db.update_user(message.from_user.id, city=city)
    await state.clear()
    await message.answer("✅ Город обновлён!", reply_markup=main_menu())

@dp.message(EditProfile.about)
async def do_edit_about(message: Message, state: FSMContext):
    about = message.text.strip()
    if len(about) > 200:
        await message.answer("❌ Максимум 200 символов:")
        return
    db.update_user(message.from_user.id, about=about)
    await state.clear()
    await message.answer("✅ Описание обновлено!", reply_markup=main_menu())

@dp.message(EditProfile.photo, F.photo)
async def do_edit_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    db.update_user(message.from_user.id, photo_id=photo_id)
    await state.clear()
    await message.answer("✅ Фото обновлено!", reply_markup=main_menu())

# ── ВКЛЮЧИТЬ / ОТКЛЮЧИТЬ АНКЕТУ ──
@dp.callback_query(F.data == "toggle_profile")
async def toggle_profile(call: CallbackQuery):
    user = db.get_user(call.from_user.id)
    new_status = not user['active']
    db.update_user(call.from_user.id, active=new_status)
    status_text = "🟢 Анкета включена — тебя снова видят!" if new_status else "🔴 Анкета отключена — тебя не видят в ленте."
    await call.answer(status_text, show_alert=True)

@dp.callback_query(F.data == "back_to_profile")
async def back_to_profile(call: CallbackQuery):
    await call.answer()

# ── ЛАЙКИ ──
@dp.message(F.text == "❤️ Лайки")
async def show_likes(message: Message):
    user = db.get_user(message.from_user.id)
    if not user:
        return

    likers = db.get_likers(message.from_user.id)
    if not likers:
        await message.answer("😔 Пока никто не поставил тебе лайк.")
        return

    await message.answer(f"❤️ <b>Тебя лайкнули {len(likers)} раз(а):</b>")
    for liker in likers[:5]:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="❤️ Ответить", callback_data=f"like:{liker['user_id']}"),
                InlineKeyboardButton(text="👎 Пропустить", callback_data=f"dislike:{liker['user_id']}")
            ]
        ])
        await send_profile_card(message.chat.id, liker, kb)

# ── МЭТЧИ ──
@dp.message(F.text == "💞 Мэтчи")
async def show_matches(message: Message):
    matches = db.get_matches(message.from_user.id)
    if not matches:
        await message.answer("😔 Мэтчей пока нет. Продолжай лайкать!")
        return

    await message.answer(f"💞 <b>Твои мэтчи ({len(matches)}):</b>")
    for match in matches:
        kb = None
        if match.get('username'):
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать", url=f"https://t.me/{match['username']}")]
            ])
        await send_profile_card(message.chat.id, match, kb)

# ── ТОП ──
@dp.message(F.text == "🔥 Топ")
async def show_top(message: Message):
    top = db.get_top_users()
    if not top:
        await message.answer("Топ пока пуст 😔")
        return

    text = "🔥 <b>Топ анкет недели:</b>\n\n"
    for i, u in enumerate(top, 1):
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
        text += f"{medal} <b>{u['name']}</b>, {u['age']} — {u['city']} — ❤️ {u['likes_received']}\n"

    await message.answer(text)

# ── НАСТРОЙКИ ──
@dp.message(F.text == "⚙️ Настройки")
async def show_settings(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Кого ищу: Всех", callback_data="filter:all")],
        [InlineKeyboardButton(text="🔎 Кого ищу: Парней", callback_data="filter:male")],
        [InlineKeyboardButton(text="🔎 Кого ищу: Девушек", callback_data="filter:female")],
        [InlineKeyboardButton(text="🗑 Удалить анкету", callback_data="delete_profile")]
    ])
    await message.answer("⚙️ <b>Настройки</b>", reply_markup=kb)
@dp.message(Command("admin_users"))
async def admin_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет доступа")
        return

    users = db.get_all_users()

    if not users:
        await message.answer("😔 Пользователей пока нет")
        return

    text = "👥 <b>Пользователи бота:</b>\n\n"

    for u in users[:50]:
        username = f"@{u['username']}" if u.get('username') else "без username"
        text += (
            f"🆔 {u['user_id']}\n"
            f"👤 {u['name']}\n"
            f"📎 {username}\n"
            f"🏙 {u['city']}\n\n"
        )

    await message.answer(text)

@dp.callback_query(F.data.startswith("filter:"))
async def set_filter(call: CallbackQuery):
    f = call.data.split(":")[1]
    db.update_user(call.from_user.id, search_filter=f)
    labels = {"all": "Всех", "male": "Парней", "female": "Девушек"}
    await call.answer(f"✅ Теперь ищешь: {labels[f]}", show_alert=True)

@dp.callback_query(F.data == "delete_profile")
async def delete_profile(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")]
    ])
    await call.message.answer("⚠️ Ты уверен? Все данные будут удалены.", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "confirm_delete")
async def confirm_delete(call: CallbackQuery):
    db.delete_user(call.from_user.id)
    await call.message.answer("🗑 Анкета удалена. Используй /start чтобы создать новую.")
    await call.answer()

@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(call: CallbackQuery):
    await call.answer("Отменено")

# ── MAIN ──
async def main():
    db.init_db()
    logger.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
