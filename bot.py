import os
import logging
import sqlite3
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    WebAppInfo,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
LANDING_URL = os.getenv("LANDING_URL", "https://example.com/")
DB_PATH = os.getenv("DB_PATH", "spcx_bot.db")

# Put one or more Telegram numeric user IDs here, separated by commas.
# Example: ADMIN_IDS=123456789,987654321
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

if not TOKEN:
    raise RuntimeError("Set BOT_TOKEN in your .env file before starting the bot.")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            starts INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def track_user(user, event="interaction", started=False):
    now = now_iso()
    conn = db()
    row = conn.execute(
        "SELECT user_id FROM users WHERE user_id = ?", (user.id,)
    ).fetchone()

    if row:
        if started:
            conn.execute(
                "UPDATE users SET username=?, first_name=?, last_seen=?, starts=starts+1 WHERE user_id=?",
                (user.username, user.first_name, now, user.id)
            )
        else:
            conn.execute(
                "UPDATE users SET username=?, first_name=?, last_seen=? WHERE user_id=?",
                (user.username, user.first_name, now, user.id)
            )
    else:
        conn.execute(
            "INSERT INTO users(user_id, username, first_name, first_seen, last_seen, starts) "
            "VALUES(?,?,?,?,?,?)",
            (user.id, user.username, user.first_name, now, now, 1 if started else 0)
        )

    conn.execute(
        "INSERT INTO events(user_id, event, created_at) VALUES(?,?,?)",
        (user.id, event, now)
    )
    conn.commit()
    conn.close()


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 Open SPCX ",
            web_app=WebAppInfo(url=LANDING_URL)
        )],
        [InlineKeyboardButton(
            text="🎁 Claim 10,000 $SPCX Tokens",
            web_app=WebAppInfo(url=LANDING_URL)
        )],
        [
            InlineKeyboardButton(text="📊 Market Snapshot", callback_data="market"),
            InlineKeyboardButton(text="🌌 Mission Timeline", callback_data="timeline")
        ],
        [
            InlineKeyboardButton(text="🛰 Business Map", callback_data="business"),
            InlineKeyboardButton(text="ℹ️ About", callback_data="about")
        ],
    ])


def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 Open SPCX ",
            web_app=WebAppInfo(url=LANDING_URL)
        )],
        [InlineKeyboardButton(text="⬅️ Main Menu", callback_data="home")],
    ])


@dp.message(CommandStart())
async def start(message: Message):
    track_user(message.from_user, "start", started=True)
    text = (
    "<b>🚀 SPCX Mission Control</b>\n\n"
"Welcome to the SPCX AI Bot companion.\n\n"
"Step into the SPCX mission hub to explore the launch experience, "
"token claim center, market activity, mission progress, business "
"ecosystem, and project overview — all in one place.\n\n"

"🎁 <b>Claim 10,000 $SPCX Tokens</b>\n"
"Enter the Claim Center to explore the available token claim "
"experience, review the claim details, and follow the instructions "
"provided for participating.\n\n"

"📊 <b>Market Snapshot</b>\n"
"Explore market-focused information, activity indicators, featured "
"figures, and the visual SPCX market experience.\n\n"

"🛰️ <b>Mission Progress</b>\n"
"Follow the SPCX mission timeline and explore key milestones, "
"technology themes, and future-focused objectives.\n\n"

"🌐 <b>Business Ecosystem</b>\n"
"Discover the broader SPCX ecosystem, including business themes, "
"connectivity, innovation, and the vision behind the project.\n\n"

"🌌 <b>Mission Hub</b>\n"
"Everything is organized in one place so you can explore SPCX, "
"check available features, and move through the mission experience "
"directly from Telegram."
            )
    await message.answer(text, reply_markup=main_menu())


@dp.message(Command("menu"))
async def menu(message: Message):
    track_user(message.from_user, "menu")
    await message.answer(
        "<b>🚀 SPCX Mission Control</b>\n\nChoose a section:",
        reply_markup=main_menu()
    )


@dp.message(Command("stats"))
async def stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("This command is available to bot administrators only.")
        return

    conn = db()
    total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    starts = conn.execute("SELECT COALESCE(SUM(starts),0) FROM users").fetchone()[0]
    events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    active_24 = conn.execute(
        "SELECT COUNT(*) FROM users WHERE last_seen >= ?", (since_24h,)
    ).fetchone()[0]
    active_7 = conn.execute(
        "SELECT COUNT(*) FROM users WHERE last_seen >= ?", (since_7d,)
    ).fetchone()[0]

    rows = conn.execute(
        "SELECT event, COUNT(*) FROM events GROUP BY event ORDER BY COUNT(*) DESC"
    ).fetchall()
    conn.close()

    event_lines = "\n".join(
        f"• {event}: <b>{count}</b>" for event, count in rows[:10]
    ) or "• No events yet"

    text = (
        "<b>📈 SPCX Bot Analytics</b>\n\n"
        f"👥 <b>Unique users:</b> {total}\n"
        f"🚀 <b>/start launches:</b> {starts}\n"
        f"🟢 <b>Active last 24h:</b> {active_24}\n"
        f"📅 <b>Active last 7 days:</b> {active_7}\n"
        f"📊 <b>Total tracked events:</b> {events}\n\n"
        "<b>Top activity</b>\n"
        f"{event_lines}\n\n"
        "<i>These are bot-side interaction metrics, not Telegram-wide "
        "impressions or ad traffic.</i>"
    )
    await message.answer(text)


@dp.callback_query(F.data == "home")
async def home(callback: CallbackQuery):
    track_user(callback.from_user, "home")
    await callback.answer()
    await callback.message.edit_text(
        "<b>🚀 SPCX Mission Control</b>\n\nChoose a section to explore:",
        reply_markup=main_menu()
    )


@dp.callback_query(F.data == "market")
async def market(callback: CallbackQuery):
    track_user(callback.from_user, "market")
    await callback.answer()
    text = (
"<b>📊 Market Snapshot</b>\n\n"
"Explore the SPCX market experience through a visual snapshot "
"of the project's market-focused presentation.\n\n"

"📈 <b>Market Scale</b>\n"
"Review the featured market figures, offering comparisons, "
"price displays, and key statistics presented throughout the SPCX experience.\n\n"

"⚡ <b>Market Activity</b>\n"
"Follow the visual indicators, animated data elements, and "
"scrolling market ticker designed to bring the SPCX interface to life.\n\n"

"🛰️ <b>Mission Perspective</b>\n"
"Connect the market story with the broader SPCX mission, "
"business ecosystem, milestones, and project narrative.\n\n"

"🔎 <b>Explore SPCX</b>\n"
"Use the SPCX menus to move between Market Snapshot, Mission Log, "
"Business Map, Claim Center, and the project overview."
    )
    await callback.message.edit_text(text, reply_markup=back_menu())


@dp.callback_query(F.data == "timeline")
async def timeline(callback: CallbackQuery):
    track_user(callback.from_user, "timeline")
    await callback.answer()
    text = (
      "<b>🌌 Mission Timeline</b>\n\n"

"<b>01 · Early Beginnings</b>\n"
"Ambitious aerospace and technology goals begin the mission story. "
"Early development focuses on engineering, innovation, spacecraft "
"systems, launch capabilities, and the long-term vision of making "
"advanced space technology more accessible.\n\n"

"<b>02 · Launch Expansion</b>\n"
"Reusable launch and access-to-orbit themes move to center stage. "
"Advances in launch systems, spacecraft operations, payload delivery, "
"and mission infrastructure create new possibilities for reaching "
"and operating in orbit.\n\n"

"<b>03 · Global Connectivity</b>\n"
"Satellite connectivity and communications become key themes. "
"Large-scale satellite networks, digital communications, data services, "
"and worldwide coverage demonstrate how orbital infrastructure can "
"extend connectivity beyond traditional terrestrial networks.\n\n"

"<b>04 · AI & Intelligence</b>\n"
"Aerospace, software, automation, and AI converge in the roadmap. "
"Intelligent computing, automated systems, data processing, and "
"software-driven operations become increasingly important themes "
"for future space and technology infrastructure.\n\n"

"<b>05 · Integrated Ecosystem</b>\n"
"Launch systems, orbital infrastructure, connectivity, software, "
"and intelligent technology increasingly operate as connected "
"parts of a broader ecosystem. This stage focuses on how different "
"technology areas can work together to support future missions.\n\n"

"<b>06 · Future Frontier</b>\n"
"The mission continues toward new opportunities across space, "
"connectivity, computing, automation, and advanced technology. "
"The future-focused roadmap explores how innovation can expand "
"the possibilities of the next generation of orbital systems.\n\n"

"<b>🚀 Follow the Mission</b>\n"
"Explore each stage of the SPCX timeline and discover how the "
"mission story connects aerospace, connectivity, intelligence, "
"and future technology."
       
    )
    await callback.message.edit_text(text, reply_markup=back_menu())


@dp.callback_query(F.data == "business")
async def business(callback: CallbackQuery):
    track_user(callback.from_user, "business")
    await callback.answer()
    text = (
  "<b>🛰 Business Map</b>\n\n"

"<b>🚀 Orbital Systems</b>\n"
"Launch vehicles, spacecraft, mission infrastructure, and advanced "
"technologies supporting access to orbit. Explore the role of launch "
"operations, spacecraft development, payload delivery, and the "
"systems required to support future space missions.\n\n"

"<b>🌐 Global Network</b>\n"
"Satellite connectivity, communications infrastructure, and worldwide "
"network concepts. This area highlights how space-based connectivity "
"can support communication, data services, remote coverage, and "
"always-connected infrastructure across different regions.\n\n"

"<b>🤖 Intelligence</b>\n"
"AI, automation, software, and advanced computing as strategic "
"technology themes. Explore how intelligent systems, automation, "
"data processing, and software platforms can contribute to more "
"efficient operations and next-generation technology.\n\n"

"<b>📡 Connectivity</b>\n"
"Explore the relationship between satellites, communications, data "
"systems, and digital infrastructure. Connectivity represents a key "
"theme within the broader SPCX ecosystem and its future-oriented "
"technology narrative.\n\n"

"<b>🛰 Mission Infrastructure</b>\n"
"From launch support to orbital operations, mission infrastructure "
"connects the different components required to move technology, "
"payloads, and information through the space environment.\n\n"

"<b>🌌 Future Technologies</b>\n"
"Discover emerging themes across space systems, communications, AI, "
"automation, and advanced computing. The Business Map brings these "
"areas together to present a broader view of the SPCX technology "
"ecosystem.\n\n"

"<b>🔭 Explore the Map</b>\n"
"Move through the SPCX experience to discover each business theme, "
"connect technology concepts with the mission narrative, and explore "
"how the different areas fit together."
    )
    await callback.message.edit_text(text, reply_markup=back_menu())


@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    track_user(callback.from_user, "about")
    await callback.answer()
    text = (
        "<b>ℹ️ About SPCX</b>\n\n"
"SPCX Mission Control brings the SPCX experience into AI Bot, "
"giving visitors a simple way to explore the project and its core features.\n\n"

"🚀 <b>Mission Center</b>\n"
"Explore the SPCX mission, launch narrative, project vision, "
"and key milestones.\n\n"

"📊 <b>Market Dashboard</b>\n"
"Explore the market-style dashboard and follow SPCX market "
"activity and project information.\n\n"

"🛰️ <b>Mission Timeline</b>\n"
"Follow the SPCX journey through key milestones and future "
"mission objectives.\n\n"

"🌐 <b>Business Ecosystem</b>\n"
"Explore business themes, technology, connectivity, and the "
"broader SPCX ecosystem.\n\n"

"🎁 <b>Claim Center</b>\n"
"Access the SPCX claim experience and explore the available "
"claim information.\n\n"

 )
    await callback.message.edit_text(text, reply_markup=back_menu())


@dp.message()
async def fallback(message: Message):
    track_user(message.from_user, "message")
    await message.answer(
        "Use /start or /menu to open SPCX Mission Control.",
        reply_markup=main_menu()
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
