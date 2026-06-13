import sqlite3
import asyncio  # Для работы asyncio.run()
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties  # Для настройки parse_mode
from aiogram.filters import CommandStart, Command
# ... остальные ваши импорты (типы, исключения и т.д.)
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    InputMediaPhoto,  # <--- НОВЫЙ ИМПОРТ
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError  # <--- НОВЫЙ ИМПОРТ

# ================== НАСТРОЙКИ ==================

TOKEN = "8857193787:AAEbOD7QJqFtpb4RB0x8qKwdOyAJAhh-Sus"

DB_PATH = "bot.db"

# админы бота (могут добавлять профиты)
ADMINS = {8501630899, 7122188634}

# ЧАТ ДЛЯ ПРОФИТОВ И КЭШИРОВАНИЯ. БОТ ДОЛЖЕН БЫТЬ АДМИНОМ!
GROUP_CHAT_ID = -1003352853772

# владелец для покупки инструментов
OWNER_USERNAME = "aIadin_work"

# ссылки на мануалы
MAIN_MANUAL = "https://t.me/+eSf2OvBs56I1NWFh"
POLAND = "https://t.me/+1WlTrCboIsI4ZjQx"
ROMANIA = "https://t.me/+IZD-YN6qnGAwZWQx"
PORTUGAL = "https://t.me/+vZ2BW3gdbdA4NmRh"
SPAIN = "https://t.me/+G2hMZTf8lKk2MWMx"
UK = "https://t.me/+l579uUfDDAMwMTQx"
BULGARIA = "https://t.me/+i6tfFsOAZw04MjQx"

PROJECT_TAG = "@Saint_legion_bot"

# --- ФАЙЛЫ КАРТИНОК (ПРОВЕРЬТЕ ИМЕНА ФАЙЛОВ В ВАШЕЙ ПАПКЕ) ---
# Если файлов нет, замените их на те, что у вас есть!
MENU_PHOTO = "welcome.png"
PROFIT_PHOTO = "profit.png"

PROFILE_PHOTO = "profile.png"
TOP_PHOTO = "top.png"
KASSA_PHOTO = "kassa.png"
INFO_PHOTO = "info.png"

MANUALS_PHOTO = "manuals.jpg"
MARKET_PHOTO = "market.png"
MENTORS_PHOTO = "mentors.png"

# --- КЭШ (будет содержать file_id) ---
IMAGE_CACHE: dict[str, str] = {}

# Список всех доступных наставников (ID : (USERNAME, ПРОЦЕНТ))
MENTORS = {
    111111111: ("aIadin_work", 25),  # Замените ID
    222222222: ("qwertyygod", 20),  # Замените ID
}

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# СЛОВАРЬ ХРАНЕНИЯ: (chat_id, user_id) -> (message_id, current_image_path)
last_messages: dict[tuple[int, int], tuple[int, str]] = {}


# ================== БАЗА ДАННЫХ И ХЕЛПЕРЫ (ОБНОВЛЕНЫ ДЛЯ КУРАТОРОВ) ==================

def get_db_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users
        (
            user_id
            INTEGER
            PRIMARY
            KEY,
            username
            TEXT,
            tag
            TEXT,
            curator
            TEXT,
            created_at
            TEXT,
            is_curator_set
            BOOLEAN
            DEFAULT
            0,
            assigned_curator_id
            INTEGER
            NULL
        )
        """
    )

    # Добавление новых колонок, если их нет
    try:
        cur.execute("ALTER TABLE users ADD COLUMN is_curator_set BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE users ADD COLUMN assigned_curator_id INTEGER NULL")
    except sqlite3.OperationalError:
        pass

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS profits
        (
            id
            INTEGER
            PRIMARY
            KEY
            AUTOINCREMENT,
            user_id
            INTEGER,
            amount
            REAL,
            country
            TEXT,
            worker_share
            REAL,
            project_share
            REAL,
            created_at
            TEXT,
            FOREIGN
            KEY
        (
            user_id
        ) REFERENCES users
        (
            user_id
        )
            )
        """
    )

    conn.commit()
    conn.close()


def add_profit_to_user(user_id: int, amount: float, country: str, worker_share: float, project_share: float):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO profits (user_id, amount, country, worker_share, project_share, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, amount, country, worker_share, project_share, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

def get_or_create_user(user) -> dict:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id, username, tag, curator, created_at, is_curator_set, assigned_curator_id FROM users WHERE user_id = ?",
        (user.id,))
    row = cur.fetchone()

    if row is None:
        username = user.username or ""
        tag = f"@{username}" if username else ""
        curator = "Не закреплён ни за кем"
        created_at = datetime.utcnow().isoformat()
        is_curator_set = 0
        assigned_curator_id = None

        cur.execute(
            "INSERT INTO users (user_id, username, tag, curator, created_at, is_curator_set, assigned_curator_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user.id, username, tag, curator, created_at, is_curator_set, assigned_curator_id),
        )
        conn.commit()
        data = {
            "user_id": user.id,
            "username": username,
            "tag": tag,
            "curator": curator,
            "created_at": created_at,
            "is_curator_set": is_curator_set,
            "assigned_curator_id": assigned_curator_id,
        }
    else:
        user_id, username_db, tag_db, curator_db, created_at, is_curator_set, assigned_curator_id = row

        # Обновляем тег/юзернейм
        username = user.username or ""
        tag = f"@{username}" if username else ""
        cur.execute(
            "UPDATE users SET username = ?, tag = ? WHERE user_id = ?",
            (username, tag, user.id),
        )
        conn.commit()

        # Формируем текст куратора для вывода
        curator_text = curator_db
        if is_curator_set and assigned_curator_id in MENTORS:
            curator_username = MENTORS[assigned_curator_id][0]
            curator_text = f"@{curator_username}"

        data = {
            "user_id": user_id,
            "username": username,
            "tag": tag,
            "curator": curator_text,
            "created_at": created_at,
            "is_curator_set": is_curator_set,
            "assigned_curator_id": assigned_curator_id,
        }

    conn.close()
    return data


def set_user_curator(user_id: int, mentor_id: int, mentor_username: str):
    conn = get_db_connection()
    cur = conn.cursor()

    curator_text = f"@{mentor_username}"

    cur.execute(
        "UPDATE users SET is_curator_set = 1, assigned_curator_id = ?, curator = ? WHERE user_id = ?",
        (mentor_id, curator_text, user_id),
    )
    conn.commit()
    conn.close()


def unset_user_curator(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()

    curator_text = "Не закреплён ни за кем"

    cur.execute(
        "UPDATE users SET is_curator_set = 0, assigned_curator_id = NULL, curator = ? WHERE user_id = ?",
        (curator_text, user_id),
    )
    conn.commit()
    conn.close()


def get_mentor_students_count(mentor_id: int) -> int:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users WHERE is_curator_set = 1 AND assigned_curator_id = ?",
        (mentor_id,),
    )
    count = cur.fetchone()[0]
    conn.close()
    return count


# Остальные функции БД (find_user_by_ref, add_profit_to_user, get_user_profit, get_team_stats, get_top_users, get_user_rank)
# оставлены без изменений, так как они не затрагивают новую логику кураторов и работают корректно.

def find_user_by_ref(ref: str):
    conn = get_db_connection()
    cur = conn.cursor()
    row = None

    if ref.startswith("@"):
        cur.execute("SELECT user_id, username, tag FROM users WHERE tag = ?", (ref,))
        row = cur.fetchone()
    else:
        try:
            uid = int(ref)
            cur.execute("SELECT user_id, username, tag FROM users WHERE user_id = ?", (uid,))
            row = cur.fetchone()
        except ValueError:
            row = None

    conn.close()
    return row




def _threshold(days: int | None):
    if days is None:
        return None
    return (datetime.utcnow() - timedelta(days=days)).isoformat()


def get_user_profit(user_id: int, days: int | None = None):
    conn = get_db_connection()
    cur = conn.cursor()

    if days is None:
        cur.execute("SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM profits WHERE user_id = ?", (user_id,))
    else:
        since = _threshold(days)
        cur.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM profits WHERE user_id = ? AND created_at >= ?",
            (user_id, since),
        )

    total, count = cur.fetchone()
    conn.close()
    return float(total or 0), int(count or 0)


def get_team_stats(days: int | None = None):
    conn = get_db_connection()
    cur = conn.cursor()

    if days is None:
        cur.execute("SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM profits")
    else:
        since = _threshold(days)
        cur.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM profits WHERE created_at >= ?",
            (since,),
        )

    total, count = cur.fetchone()
    conn.close()
    return float(total or 0), int(count or 0)


def get_top_users(days: int | None = None, limit: int = 10):
    conn = get_db_connection()
    cur = conn.cursor()

    if days is None:
        cur.execute(
            """
            SELECT u.user_id,
                   u.username,
                   u.tag,
                   COALESCE(SUM(p.amount), 0) AS total,
                   COUNT(p.id)                as cnt
            FROM users u
                     JOIN profits p ON p.user_id = u.user_id
            GROUP BY u.user_id
            ORDER BY total DESC LIMIT ?
            """,
            (limit,),
        )
    else:
        since = _threshold(days)
        cur.execute(
            """
            SELECT u.user_id,
                   u.username,
                   u.tag,
                   COALESCE(SUM(p.amount), 0) AS total,
                   COUNT(p.id)                as cnt
            FROM users u
                     JOIN profits p ON p.user_id = u.user_id
            WHERE p.created_at >= ?
            GROUP BY u.user_id
            ORDER BY total DESC LIMIT ?
            """,
            (since, limit),
        )

    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append(
            (int(r[0]), r[1] or "", r[2] or "", float(r[3] or 0), int(r[4] or 0))
        )
    return result


def get_user_rank(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT u.user_id, COALESCE(SUM(p.amount), 0) AS total
        FROM users u
                 JOIN profits p ON p.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY total DESC
        """
    )
    rows = cur.fetchall()
    conn.close()

    for idx, (uid, _) in enumerate(rows, start=1):
        if uid == user_id:
            return idx
    return None


def format_money(x: float) -> str:
    s = f"{x:.2f}"
    s = s.rstrip("0").rstrip(".")
    if s == "":
        s = "0"
    return s


def days_by_mode(mode: str) -> int | None:
    if mode == "all":
        return None
    if mode == "day":
        return 1
    if mode == "week":
        return 7
    if mode == "month":
        return 30
    return None


COUNTRY_CODES = {
    "PL": "Польша🇵🇱",
    "RO": "Румыния🇷🇴",
    "PT": "Португалия🇵🇹",
    "ES": "Испания🇪🇸",
    "UK": "Великобритания🇬🇧",
    "BG": "Болгария🇧🇬",
}


def country_from_code(code: str) -> str:
    code = code.upper()
    return COUNTRY_CODES.get(code, code)


# --- ФУНКЦИИ ДЛЯ КЭШИРОВАНИЯ ---

async def cache_single_photo(image_path: str) -> bool:
    """Кэширует file_id, отправляя фото в GROUP_CHAT_ID (НУЖЕН ВАШ ЧАТ)."""
    if image_path in IMAGE_CACHE:
        return True

    try:
        # Отправляем фото в служебный чат, чтобы получить file_id
        msg = await bot.send_photo(
            chat_id=GROUP_CHAT_ID,
            photo=FSInputFile(image_path),
            caption="."  # Нужна хоть какая-то подпись
        )

        file_id = msg.photo[-1].file_id
        IMAGE_CACHE[image_path] = file_id

        # Удаляем сообщение
        await bot.delete_message(chat_id=GROUP_CHAT_ID, message_id=msg.message_id)

        print(f"✅ Кэш: Успешно закэширован file_id для {image_path}")
        return True

    except TelegramForbiddenError:
        print(f"❌ Кэш: Не удалось закэшировать {image_path}. Проверьте права бота в чате {GROUP_CHAT_ID}.")
        return False
    except FileNotFoundError:
        print(f"❌ Кэш: Файл не найден: {image_path}. Убедитесь, что файл существует.")
        return False
    except Exception as e:
        print(f"❌ Кэш: Критическая ошибка при кэшировании {image_path}: {e}")
        return False


async def cache_all_photos_on_start():
    """Прогревает кэш для всех используемых медиафайлов."""
    print("--- Прогрев медиа-кэша... ---")

    # Собираем все уникальные пути
    files_to_cache = {
        MENU_PHOTO, PROFIT_PHOTO, PROFILE_PHOTO, TOP_PHOTO, KASSA_PHOTO,
        INFO_PHOTO, MANUALS_PHOTO, MARKET_PHOTO, MENTORS_PHOTO
    }

    for file in files_to_cache:
        await cache_single_photo(file)

    print("--- Прогрев медиа-кэша завершен. ---")


# --- ГЛАВНАЯ ФУНКЦИЯ РЕДАКТИРОВАНИЯ/ОТПРАВКИ (СУТЬ АНТИ-МИГАНИЯ) ---

async def handle_menu_action(
    user_id: int,
    chat_id: int,
    image_path: str,
    caption: str,
    kb: InlineKeyboardMarkup,
    message: Message | CallbackQuery | None = None
):
    """
    SPA-логика: ОДНО сообщение на пользователя.
    /start -> send
    callback -> edit (БЕЗ УДАЛЕНИЙ)
    """
    key = (chat_id, user_id)
    last_msg_info = last_messages.get(key)

    old_id = last_msg_info[0] if last_msg_info else None
    current_image_path = last_msg_info[1] if last_msg_info else None

    photo_data = IMAGE_CACHE.get(image_path) or FSInputFile(image_path)

    # ================= CALLBACK =================
    if isinstance(message, CallbackQuery):
        await message.answer()
        msg = message.message  # ⚠️ ЭТО И ЕСТЬ НУЖНОЕ СООБЩЕНИЕ

        try:
            if image_path == current_image_path:
                await msg.edit_caption(
                    caption=caption,
                    reply_markup=kb
                )
            else:
                media = InputMediaPhoto(
                    media=photo_data,
                    caption=caption
                )
                await msg.edit_media(
                    media=media,
                    reply_markup=kb
                )

            last_messages[key] = (msg.message_id, image_path)
            return

        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return
            print("❌ EDIT ERROR:", e)

    # ================= /start или fallback =================
    sent = await bot.send_photo(
        chat_id=chat_id,
        photo=photo_data,
        caption=caption,
        reply_markup=kb,
    )

    last_messages[key] = (sent.message_id, image_path)



# ================== ХЕНДЛЕРЫ МЕНЮ ==================

@router.message(CommandStart())
async def cmd_start(message: Message):
    init_db()
    get_or_create_user(message.from_user)

    # Получаем данные из БД
    payout = get_total_payouts()
    workers = get_total_workers_count()

    caption = (
        "🎯 <b>Добро пожаловать, воркер @</b>"
        f"<b>{message.from_user.username or 'без_ника'}!</b>\n\n"
        f"<b>• Выплачено всего:</b> <code>{payout}$</code>\n"
        "<b>• Работаем с 2025 года</b>\n"
        f"<b>• Воркеров в боте: </b><code>{workers}</code>\n\n"
        "<blockquote><code>🛟Выберите нужный раздел из меню ниже </code></blockquote>"
    )

    await handle_menu_action(
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        image_path=MENU_PHOTO,
        caption=caption,
        kb=main_menu_kb(),
        message=message
    )

def get_total_payouts() -> str:
    """Вспомогательная функция для получения красивой суммы всех профитов"""
    try:
        # Используем вашу существующую функцию get_team_stats
        # Она возвращает (total_amount, count)
        total_sum, _ = get_team_stats(days=None)
        return format_money(total_sum)
    except Exception as e:
        print(f"Ошибка при получении общей кассы: {e}")
        return "0"

def get_total_workers_count() -> int:
    """Считает общее количество юзеров в базе"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0

@router.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery):
    await callback.answer()

    # Получаем данные из БД
    payout = get_total_payouts()
    workers = get_total_workers_count()

    caption = (
        "🎯 <b>Добро пожаловать, воркер @</b>"
        f"<b>{callback.from_user.username or 'без_ника'}!</b>\n\n"
        f"<b>• Выплачено всего:</b> <code>{payout}$</code>\n"
        "<b>• Работаем с 2025 года</b>\n"
        f"<b>• Воркеров в боте: </b><code>{workers}</code>\n\n"
        "<blockquote><code>🛟Выберите нужный раздел из меню ниже </code></blockquote>"
    )

    await handle_menu_action(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        image_path=MENU_PHOTO,
        caption=caption,
        kb=main_menu_kb(),
        message=callback
    )


@router.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery):
    await callback.answer()
    init_db()
    user_data = get_or_create_user(callback.from_user)

    user_id = user_data["user_id"]
    day_sum, _ = get_user_profit(user_id, days=1)
    month_sum, _ = get_user_profit(user_id, days=30)
    total_sum, count = get_user_profit(user_id, days=None)

    rank = get_user_rank(user_id)
    place_text = f"#{rank}" if rank is not None else "Не в топе"

    curator_text = user_data['curator']

    caption = (
        "— ℹ️ <b>Информация о профиле:</b>\n\n"
        f"• <b>ID: <code>{user_id}</code>\n</b>"
        f"• <b>Имя в выплатах: {user_data['tag'] or '—'}\n</b>"
        f"• <b>Количество профитов: {count}\n\n</b>"
        "⌵ <b>Информация о профитах:</b>\n"
        f"• <b>День:</b> <code> {format_money(day_sum)}$\n</code>"
        f"• <b>Месяц:</b> <code> {format_money(month_sum)}$\n</code>"
        f"• <b>Все время:</b> <code> {format_money(total_sum)}$\n\n</code>"
        "›❗ <b>Дополнительно информация:</b>\n\n"
        f"<b>• Куратор: {curator_text}</b>\n"
        f"<b>• Место в топе: {place_text}</b>"
    )

    await handle_menu_action(
        user_id=user_id,
        chat_id=callback.message.chat.id,
        image_path=PROFILE_PHOTO,
        caption=caption,
        kb=back_main_kb(),
        message=callback
    )


async def show_top(callback: CallbackQuery, mode: str):
    days = days_by_mode(mode)
    top_users = get_top_users(days=days, limit=10)

    if mode == "day":
        title = "<b>🏆 Топ воркеров ЗА ДЕНЬ:</b>"
    elif mode == "week":
        title = "<b>🏆 Топ воркеров ЗА НЕДЕЛЮ:</b>"
    elif mode == "month":
        title = "<b>🏆 Топ воркеров ЗА МЕСЯЦ:</b>"
    else:
        title = "<b>🏆 Топ воркеров (за всё время):</b>"

    lines = [f"{title}\n"]
    if not top_users:
        lines.append("<b>Пока нет профитов 😔</b>")
    else:
        for idx, (_, username, tag, total, cnt) in enumerate(top_users, start=1):
            name = f"<b>@{username}</b>" if username else (tag or "Без ника")
            lines.append(
                f"{idx}. {name} — <b>{format_money(total)}$ × {cnt} профитов</b>"
            )

    total, cnt = get_team_stats(days=days)
    lines.append(f"\n— 💼 <b>Общая касса за период: {format_money(total)}$ ({cnt} профитов)</b>")

    caption = "\n".join(lines)

    await handle_menu_action(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        image_path=TOP_PHOTO,
        caption=caption,
        kb=top_kb(),
        message=callback
    )


@router.callback_query(F.data.in_({"top_all", "top_day", "top_week", "top_month"}))
async def cb_top(callback: CallbackQuery):
    await callback.answer()
    mode = callback.data.split("_")[1]
    await show_top(callback, mode)


async def show_kassa(callback: CallbackQuery, mode: str):
    days = days_by_mode(mode)

    all_total, all_cnt = get_team_stats(None)
    period_total, period_cnt = get_team_stats(days=days or 1)

    if mode == "day":
        period_name = "сегодня"
    elif mode == "week":
        period_name = "за 7 дней"
    elif mode == "month":
        period_name = "за 30 дней"
    else:
        period_name = "за всё время"

    caption = (
        "— 🎭 <b>Касса команды</b>\n\n"
        "<blockquote>📊 <b>За всё время:</b></blockquote>\n"
        f"<b>• Сумма:</b><code> {format_money(all_total)}$</code>\n"
        f"<b>• Количество профитов:</b><code> {all_cnt}</code>\n\n"
        f"<blockquote>📊 <b>За период ({period_name}):</b></blockquote>\n"
        f"<b>• Сумма:</b><code> {format_money(period_total)}$</code>\n"
        f"<b>• Количество профитов:</b><code> {period_cnt}</code>"
    )

    await handle_menu_action(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        image_path=KASSA_PHOTO,
        caption=caption,
        kb=kassa_kb(),
        message=callback
    )


@router.callback_query(F.data.in_({"kassa_all", "kassa_day", "kassa_week", "kassa_month"}))
async def cb_kassa_period(callback: CallbackQuery):
    await callback.answer()
    mode = callback.data.split("_")[1]
    await show_kassa(callback, mode)


@router.callback_query(F.data == "mentors_menu")
async def cb_mentors(callback: CallbackQuery):
    await callback.answer()

    user_data = get_or_create_user(callback.from_user)
    is_set = user_data["is_curator_set"]
    current_curator = user_data["curator"]
    current_mentor_id = user_data["assigned_curator_id"]

    if is_set:
        # Режим "Уже закреплен"
        mentor_id = current_mentor_id
        mentor_username, mentor_share = MENTORS.get(mentor_id, (None, None))
        students_count = get_mentor_students_count(mentor_id)

        if mentor_username:
            caption = (
                f"👨‍🏫 <b>Информация о Наставнике</b>\n\n"
                f"<b>• Куратор:</b> {current_curator}\n"
                f"<b>• Процент:</b> <code>{mentor_share}%</code>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"<blockquote><b>• На обучении:</b> <code>{students_count}</code></blockquote>\n\n"
                "<b>Описание:</b>\n"
                "<blockquote>Профессиональный наставник. По всем вопросам пиши ему напрямую.</blockquote>\n\n"
                "❗ <b>Если ты хочешь сменить куратора, сначала открепись.</b>"
            )
        else:
            caption = (
                f"✅ <b>Ты закреплён за: {current_curator} (ID: {current_mentor_id})</b>\n"
                "К сожалению, данные этого наставника не найдены в списке MENTORS.\n\n"
                "❗ <b>Для смены куратора, пожалуйста, открепись.</b>"
            )

    else:
        # Режим "Список для выбора"
        caption = (
            "<b>Если ты новенький и ничего не понимаешь, бери одного из наставников — "
            "они доведут тебя до первого профита меньше чем за 3 дня ✅</b>\n\n"
        )

        for mentor_id, (username, share) in MENTORS.items():
            students_count = get_mentor_students_count(mentor_id)
            caption += f"️ ️<blockquote>️️️️▪️ @{username} — {share}% ({students_count} на обучении)</blockquote>\n"

        caption += "\n<b>❗ Пиши только одному наставнику, не спамь ❗</b>"

    await handle_menu_action(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        image_path=MENTORS_PHOTO,
        caption=caption,
        kb=mentors_kb(is_set, current_mentor_id),
        message=callback
    )


@router.callback_query(F.data.startswith("select_mentor_"))
async def cb_select_mentor(callback: CallbackQuery):
    await callback.answer()

    mentor_id_str = callback.data.split("_")[-1]

    try:
        mentor_id = int(mentor_id_str)
    except ValueError:
        return await callback.answer("Ошибка ID наставника.")

    if mentor_id not in MENTORS:
        return await callback.answer("Наставник не найден.")

    mentor_username, mentor_share = MENTORS[mentor_id]
    students_count = get_mentor_students_count(mentor_id)

    caption = (
        f"👨‍🏫 <b>Информация о Наставнике</b>\n\n"
        f"<b>• Юзернейм:</b> @{mentor_username}\n"
        f"<b>• Процент:</b> <code>{mentor_share}%</code>\n\n"
        f"<blockquote>📊 <b>Статистика:</b></blockquote>\n"
        f"<blockquote>• На обучении: <code>{students_count}</code></blockquote>\n\n"
        "📝 <b>Описание:</b>\n"
        "<blockquote>Профессиональный наставник</blockquote>\n\n"
    )

    await handle_menu_action(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        image_path=MENTORS_PHOTO,
        caption=caption,
        kb=confirm_mentor_kb(mentor_id),
        message=callback
    )


@router.callback_query(F.data.startswith("set_mentor_"))
async def cb_set_mentor(callback: CallbackQuery):
    await callback.answer()

    mentor_id_str = callback.data.split("_")[-1]

    try:
        mentor_id = int(mentor_id_str)
    except ValueError:
        return await callback.answer("Ошибка ID наставника.")

    if mentor_id not in MENTORS:
        return await callback.answer("Наставник не найден.")

    user_data = get_or_create_user(callback.from_user)
    if user_data.get("is_curator_set"):
        return await callback.answer(
            f"Ты уже закреплён за {user_data['curator']}. Повторное закрепление невозможно!",
            show_alert=True
        )

    mentor_username, _ = MENTORS[mentor_id]
    set_user_curator(callback.from_user.id, mentor_id, mentor_username)

    students_count = get_mentor_students_count(mentor_id)

    caption = (
        "🎓 <b>Успешное закрепление!</b>\n\n"
        f"✅ <b>Ты закреплён за: @{mentor_username}</b>\n\n"
        f"<blockquote>📊 <b>На обучении у куратора:</b> <code>{students_count}</code></blockquote>\n\n"
        "Теперь напиши ему, чтобы начать работу! ✅"
    )

    await handle_menu_action(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        image_path=MENU_PHOTO,  # Возвращаем на главную
        caption=caption,
        kb=main_menu_kb(),
        message=callback
    )


@router.callback_query(F.data == "unset_mentor")
async def cb_unset_mentor(callback: CallbackQuery):
    await callback.answer(text="Ты открепился от наставника.", show_alert=True)

    unset_user_curator(callback.from_user.id)

    # Снова показываем список наставников

    caption = (
        "<b>Если ты новенький и ничего не понимаешь, бери одного из наставников — "
        "они доведут тебя до первого профита ✅</b>\n\n"
    )
    for mentor_id, (username, share) in MENTORS.items():
        students_count = get_mentor_students_count(mentor_id)
        caption += f"️ ️<blockquote>️️️▪️ @{username} — {share}% ({students_count} на обучении)</blockquote>\n"

    caption += "\n<b>❗ Пиши только одному наставнику, не спамь ❗</b>"

    await handle_menu_action(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        image_path=MENTORS_PHOTO,
        caption=caption,
        kb=mentors_kb(is_set=False, current_mentor_id=None),
        message=callback
    )


@router.callback_query(F.data == "manuals")
async def cb_manuals(callback: CallbackQuery):
    await callback.answer()

    caption = " <b>Мануалы по странам</b> 👇"

    await handle_menu_action(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        image_path=MANUALS_PHOTO,
        caption=caption,
        kb=manuals_kb(),
        message=callback
    )


@router.callback_query(F.data == "tools")
async def cb_tools(callback: CallbackQuery):
    await callback.answer()

    caption = (
        "<b>Все для уверенного и стабильного ворка:</b>\n"
    )

    await handle_menu_action(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        image_path=MARKET_PHOTO,
        caption=caption,
        kb=tools_kb(),
        message=callback
    )


@router.callback_query(F.data.in_({"tool_esim", "tool_whatsapp", "tool_proxy"}))
async def cb_tool_item(callback: CallbackQuery):
    await callback.answer()

    if callback.data == "tool_esim":
        caption = (
            " <b>Название товара: E-sim</b>\n\n"
            "<b>• Название: E-sim</b>\n\n"
            "<b>• Описание: Быстрое подключение</b>\n\n"
            "<b>• Подходит под любые платформы</b>\n\n"
            "<b>• Готово к работе сразу</b>\n\n"
            "— 💰 <b>Цена:</b> 13"
        )
    elif callback.data == "tool_whatsapp":
        caption = (
            " <b>Название товара: Whatsapp</b>\n\n"
            "<b>• Описание: Быстрое подключение.</b>\n"
            "<b>Готово к работе сразу.</b>\n\n"
            "— 💰 <b>Цена:</b> 10"
        )
    else:
        caption = (
            " <b>Название товара: Proxy</b>\n\n"
            "<b>• Описание: Выдача на пк/телефон.</b>\n\n"
            "— 💰 <b>Цена:</b> 7"
        )

    await handle_menu_action(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        image_path=MARKET_PHOTO,
        caption=caption,
        kb=tool_buy_kb(),
        message=callback
    )


@router.callback_query(F.data == "info")
async def cb_info(callback: CallbackQuery):
    await callback.answer()

    caption = (
        "<b>- 🎡 Информация по боту</b>\n\n"
        "✅ <b>Разделы бота:</b>\n\n"
        "<blockquote>• <b>Профиль — ваша статистика и информация</b></blockquote>\n"
        "<blockquote>• <b>Топ воркеров — рейтинг за всё время и периоды</b></blockquote>\n"
        "<blockquote>• <b>Касса — общая статистика команды</b></blockquote>\n"
        "<blockquote>• <b>Мануалы — обучение по странам</b></blockquote>\n"
        "<blockquote>• <b>Маркет — покупка нужных товаров</b></blockquote>\n\n"
        "<i>По вопросам обращайтесь к администрации.</i>"
    )

    await handle_menu_action(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        image_path=INFO_PHOTO,
        caption=caption,
        kb=back_main_kb(),
        message=callback
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMINS:
        return

    total_all, cnt_all = get_team_stats(None)
    total_day, cnt_day = get_team_stats(1)

    text = (
        "🛠 <b>Админ-панель</b>\n\n"
        f"👥 Всего профитов: {cnt_all}\n"
        f"💰 Общая касса: {format_money(total_all)}$\n\n"
        f"За сегодня: {format_money(total_day)}$ ({cnt_day} профитов)\n\n"
        "Команда добавления профита:\n"
        "<code>/profit @username 100 UK</code>\n"
        "Коды стран: PL, RO, PT, ES, UK, BG"
    )

    try:
        await message.delete()
    except Exception:
        pass

    # Отправка нового сообщения в чат с командой
    sent = await message.answer(text)
    last_messages[(message.chat.id, message.from_user.id)] = (sent.message_id,
                                                              MENU_PHOTO)  # Считаем, что админка - это как главное меню


@router.message(Command("profit"))
async def cmd_profit(message: Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔ У тебя нет доступа к этой команде.")

    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        return await message.answer(
            "❗ Формат:\n"
            "<code>/profit @username 100 UK</code>\n"
            "где UK — код страны (PL, RO, PT, ES, UK, BG)"
        )

    target = parts[1]
    amount_str = parts[2]
    country_code = parts[3]

    try:
        amount = float(amount_str.replace(",", "."))
    except ValueError:
        return await message.answer("❗ Сумма должна быть числом, пример: 100 или 99.5")

    row = find_user_by_ref(target)
    if not row:
        return await message.answer("❗ Пользователь не найден в базе. Он должен сначала нажать /start.")

    user_id = int(row[0])
    username = row[1] or ""
    tag = row[2] or (f"@{username}" if username else f"ID:{user_id}")

    # 75% воркеру, 25% проекту
    worker_share = round(amount * 0.75, 2)
    project_share = round(amount - worker_share, 2)

    country_text = country_from_code(country_code)

    # сохранить профит в БД
    add_profit_to_user(user_id, amount, country_text, worker_share, project_share)

    # текст поста профита
    profit_text = (
        "<b>- "
        "PROFIT / УСПЕШНАЯ ОПЕРАЦИЯ</b>\n\n"
        f"<b>┠ Воркер: {tag}</b>\n"
        f"<b>┠ Сумма:</b><code> {format_money(amount)}$</code>\n"
        f"<b>┠ Доля воркера:</b><code> {format_money(worker_share)}$</code>\n"
        f"<b>┗ Страна: {country_text}</b>\n\n"
        "<b>🏛️ Проект:</b>\n"
        f"<b>{PROJECT_TAG}</b>"
    )

    try:
        await message.delete()
    except Exception:
        pass

    # Используем кэш для картинки профита
    photo_data = IMAGE_CACHE.get(PROFIT_PHOTO) or FSInputFile(PROFIT_PHOTO)

    try:
        profit_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🤖",
                        url="https://t.me/saint_legion_bot"
                    )
                ]
            ]
        )

        await bot.send_photo(
            chat_id=GROUP_CHAT_ID,
            photo=photo_data,
            caption=profit_text,
            reply_markup=profit_kb
        )
        await message.answer("✅ Профит отправлен и сохранён в статистике.")
    except Exception as e:
        print(f"❌ Ошибка отправки профита в групповой чат: {e}")
        await message.answer(f"✅ Профит сохранён в базе, но не отправлен в групповой чат. Ошибка: {e}")

        # ... (твой код выше: поиск user_id в базе по target) ...

        # Текст сообщения как на скриншоте (обычные эмодзи)
        worker_text = (
            f"⚙️ <b>Вы получили новый профит!</b>\n\n"
            f"🌍 <b>Страна:</b> {country_from_code(country_code)}\n"
            f"🤝 <b>Ваша доля:</b> {amount_str}$\n"
            f"— 🎓 <b>Ваш наставник:</b>\n"
            f"@{MENTORS.get(user_data['assigned_curator_id'], ['admin'])[0]}\n\n"
            f"🔥 ⌵ <b>Чтобы забрать профит напишите админу в личные сообщения по кнопке внизу!</b>"
        )

        # Кнопки как на скриншоте
        worker_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="› Написать админу ↗️", url=f"https://t.me/{OWNER_USERNAME}")],
            [InlineKeyboardButton(text="› Посмотреть профит ↗️", callback_data="profile")]
        ])

        # Отправка воркеру в личку
        try:
            await bot.send_message(
                chat_id=user_id,  # ID воркера, которого нашли выше
                text=worker_text,
                reply_markup=worker_kb
            )
        except Exception as e:
            print(f"Не удалось отправить ЛС воркеру: {e}")


# --- КЛАВИАТУРЫ (ОБНОВЛЕНЫ И СТРУКТУРИРОВАНЫ) ---

def main_menu_kb() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        ],
        [
            InlineKeyboardButton(text="🏆 Топ", callback_data="top_all"),
            InlineKeyboardButton(text="🎡 Информация", callback_data="info"),
        ],
        [
            InlineKeyboardButton(text="💸 Касса", callback_data="kassa_all"),
            InlineKeyboardButton(text="🎓 Наставники", callback_data="mentors_menu"),
        ],
        [
            InlineKeyboardButton(text="📚 Мануалы", callback_data="manuals"),
            InlineKeyboardButton(text="🛒 Маркет", callback_data="tools"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_main_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="« Назад", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- КЛАВИАТУРЫ (ОБНОВЛЕНЫ И СТРУКТУРИРОВАНЫ) ---

# ... (остальные функции kb остаются без изменений) ...

def top_kb() -> InlineKeyboardMarkup:
    """Клавиатура Топ-воркеров с кнопкой 'За все время' сверху."""
    buttons = [
        [InlineKeyboardButton(text="• За все время", callback_data="top_all")],  # <-- ЭТА СТРОКА СТАЛА ОТДЕЛЬНОЙ
        [
            InlineKeyboardButton(text="• День", callback_data="top_day"),
            InlineKeyboardButton(text="• Неделя", callback_data="top_week"),
            InlineKeyboardButton(text="• Месяц", callback_data="top_month"),
        ],
        [InlineKeyboardButton(text="« Назад", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ... (остальные функции kb остаются без изменений) ...


def kassa_kb() -> InlineKeyboardMarkup:
    # ... (Оставьте как есть) ...
    # Я также отредактирую kassa_kb, чтобы она соответствовала вашему скриншоту Топа

    buttons = [
        [InlineKeyboardButton(text="• За все время", callback_data="kassa_all")],  # Добавлено для консистентности
        [
            InlineKeyboardButton(text="• День", callback_data="kassa_day"),
            InlineKeyboardButton(text="• Неделя", callback_data="kassa_week"),
            InlineKeyboardButton(text="• Месяц", callback_data="kassa_month"),
        ],
        [InlineKeyboardButton(text="« Назад", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def manuals_kb() -> InlineKeyboardMarkup:
    # Клавиатура Мануалов (как в прошлом коде, но в вертикальном виде)
    buttons = [
        [InlineKeyboardButton(text="👑 Главный мануал", url=MAIN_MANUAL)],
        [InlineKeyboardButton(text="🇵🇱 Польша", url=POLAND)],
        [InlineKeyboardButton(text="🇷🇴 Румыния", url=ROMANIA)],
        [InlineKeyboardButton(text="🇵🇹 Португалия", url=PORTUGAL)],
        [InlineKeyboardButton(text="🇪🇸 Испания", url=SPAIN)],
        [InlineKeyboardButton(text="🇬🇧 Великобритания", url=UK)],
        [InlineKeyboardButton(text="🇧🇬 Болгария", url=BULGARIA)],
        [InlineKeyboardButton(text="« Назад", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tools_kb() -> InlineKeyboardMarkup:
    # Клавиатура Маркета (по одной кнопке в ряд, как вы просили)
    buttons = [
        [InlineKeyboardButton(text="E-sim", callback_data="tool_esim")],
        [InlineKeyboardButton(text="Whatsapp", callback_data="tool_whatsapp")],
        [InlineKeyboardButton(text="Proxy", callback_data="tool_proxy")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tool_buy_kb() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="☎️ Покупка и вопросы", url=f"https://t.me/{OWNER_USERNAME}"),
        ],
        [InlineKeyboardButton(text="« Назад", callback_data="tools")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def mentors_kb(is_set: bool, current_mentor_id: int | None) -> InlineKeyboardMarkup:
    """Клавиатура для меню Наставников (динамическая)."""
    buttons = []

    if not is_set:
        # Список доступных наставников для выбора (максимум 2 в ряд)
        row = []
        for mentor_id, (username, _) in MENTORS.items():
            row.append(InlineKeyboardButton(text=f"@{username}", callback_data=f"select_mentor_{mentor_id}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    else:
        # Кнопки "Написать" и "Открепиться"
        mentor_username, _ = MENTORS.get(current_mentor_id, ("Куратор не найден", None))
        buttons.append([
            InlineKeyboardButton(text=" Открепиться", callback_data="unset_mentor"),
        ])

    buttons.append([InlineKeyboardButton(text="« Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_mentor_kb(mentor_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения закрепления."""
    buttons = [
        [
            InlineKeyboardButton(text="🔗 Закрепиться", callback_data=f"set_mentor_{mentor_id}"),
        ],
        [InlineKeyboardButton(text="« Назад", callback_data="mentors_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ================== ЗАПУСК ==================

async def main():
    init_db()
    await cache_all_photos_on_start()
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    print("\n--- СТАРТ ---\nЗапущена версия v14: Реализовано плавное редактирование и система закрепления за Наставниками.")
    print("Убедитесь, что в папке есть все необходимые файлы картинок, и что ID наставников в MENTORS корректны.")
    asyncio.run(main())