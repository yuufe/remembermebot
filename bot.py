import os
import json
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters
)

# ─── CONFIG ───
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВСТАВЬ_ТОКЕН_СЮДА")
CHAT_ID   = int(os.environ.get("CHAT_ID", "0"))
DATA_FILE = "promises.json"

# ─── DEFAULT PROMISES ───
DEFAULT_PROMISES = [
    {"id": 1, "text": "Отправить доставку",                              "type": "once",    "done": False},
    {"id": 2, "text": "Не обзывать себя",                                "type": "regular", "done": False},
    {"id": 3, "text": "Платить за курсы по истории",                     "type": "regular", "done": False},
    {"id": 4, "text": "Купить всё для волос",                            "type": "once",    "done": False},
    {"id": 5, "text": "Помочь с Apple Pay",                              "type": "meeting", "done": False},
    {"id": 6, "text": "Сходить за кремом",                               "type": "meeting", "done": False},
    {"id": 7, "text": "Когда она расстроена — не молчать, присутствовать","type": "regular", "done": False},
    {"id": 8, "text": "Быть внимательным к мелочам",                     "type": "regular", "done": False},
]

RULES = [
    "Не обещай если не уверен на 100%. Лучше «постараюсь» — и сделать.",
    "Один срыв — это один срыв. Не «я снова тот же». Просто один срыв.",
    "Когда она расстроена — не решай, просто будь рядом: «Я здесь».",
    "Записывай обещание сразу в момент когда даёшь его.",
    "Изменения ради себя устойчивее, чем изменения под давлением.",
    "Её «не скучаю» — не правда о чувствах, а защитный механизм.",
    "Меньше слов о том что меняешься. Больше тихих действий.",
    "Тревога говорит «она охладела». Проверь — правда ли это.",
]

# ─── DATA ───
def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    data = {"promises": DEFAULT_PROMISES[:], "next_id": 9}
    save(data)
    return data

def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── HELPERS ───
def build_list(promises, show_done=False):
    active = [p for p in promises if not p["done"]]
    done   = [p for p in promises if p["done"]]
    
    TYPE_LABEL = {"once": "разовое", "regular": "регулярное", "meeting": "при встрече"}
    
    lines = [f"📋 *Активные обещания ({len(active)})*\n"]
    if active:
        for p in active:
            lines.append(f"• [{p['id']}] {p['text']}  _({TYPE_LABEL.get(p['type'], '')})_")
    else:
        lines.append("✨ Все выполнены!")
    
    if show_done and done:
        lines.append(f"\n✅ *Выполнено ({len(done)})*")
        for p in done:
            lines.append(f"~• {p['text']}~")
    
    lines.append(f"\n_Выполнено: {len(done)}/{len(promises)}_")
    return "\n".join(lines)

def daily_rule():
    return RULES[datetime.now().day % len(RULES)]

# ─── COMMANDS ───
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Трекер обещаний запущен*\n\n"
        "Команды:\n"
        "/list — список активных обещаний\n"
        "/all — все, включая выполненные\n"
        "/done 3 — отметить #3 выполненным\n"
        "/undone 3 — вернуть в активные\n"
        "/add Текст обещания — добавить новое\n"
        "/delete 3 — удалить обещание\n"
        "/rule — правило дня\n"
        "/remind — напомнить сейчас\n"
        "/reset — сбросить все к началу\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    await update.message.reply_text(build_list(data["promises"]), parse_mode="Markdown")

async def cmd_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    await update.message.reply_text(build_list(data["promises"], show_done=True), parse_mode="Markdown")

async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Укажи номер: /done 3")
        return
    pid = int(args[0])
    data = load()
    p = next((x for x in data["promises"] if x["id"] == pid), None)
    if not p:
        await update.message.reply_text(f"Обещание #{pid} не найдено")
        return
    p["done"] = True
    p["done_at"] = datetime.now().strftime("%d.%m.%Y")
    save(data)
    active = len([x for x in data["promises"] if not x["done"]])
    await update.message.reply_text(
        f"✅ Выполнено: *{p['text']}*\n\nОсталось активных: {active}",
        parse_mode="Markdown"
    )

async def cmd_undone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Укажи номер: /undone 3")
        return
    pid = int(args[0])
    data = load()
    p = next((x for x in data["promises"] if x["id"] == pid), None)
    if not p:
        await update.message.reply_text(f"Обещание #{pid} не найдено")
        return
    p["done"] = False
    p.pop("done_at", None)
    save(data)
    await update.message.reply_text(f"↩️ Возвращено в активные: *{p['text']}*", parse_mode="Markdown")

async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = " ".join(ctx.args).strip()
    if not text:
        await update.message.reply_text("Напиши что обещаешь: /add Позвонить маме")
        return
    data = load()
    new_p = {"id": data["next_id"], "text": text, "type": "once", "done": False,
             "created_at": datetime.now().strftime("%d.%m.%Y")}
    data["promises"].append(new_p)
    data["next_id"] += 1
    save(data)
    await update.message.reply_text(
        f"➕ Добавлено: *{text}*\n\n_Записано — значит существует._",
        parse_mode="Markdown"
    )

async def cmd_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Укажи номер: /delete 3")
        return
    pid = int(args[0])
    data = load()
    before = len(data["promises"])
    data["promises"] = [x for x in data["promises"] if x["id"] != pid]
    if len(data["promises"]) == before:
        await update.message.reply_text(f"Обещание #{pid} не найдено")
        return
    save(data)
    await update.message.reply_text(f"🗑 Обещание #{pid} удалено")

async def cmd_rule(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"💡 *Правило дня:*\n\n{daily_rule()}", parse_mode="Markdown")

async def cmd_remind(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    await update.message.reply_text(build_list(data["promises"]), parse_mode="Markdown")

async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = {"promises": DEFAULT_PROMISES[:], "next_id": 9}
    for p in data["promises"]:
        p["done"] = False
    save(data)
    await update.message.reply_text("♻️ Список сброшен к исходным обещаниям")

# ─── SCHEDULED REMINDERS ───
async def morning_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    active = [p for p in data["promises"] if not p["done"]]
    if not active:
        msg = "🌅 Доброе утро!\n\n✨ Все обещания выполнены. Отличная работа."
    else:
        lines = "\n".join(f"• [{p['id']}] {p['text']}" for p in active)
        msg = f"🌅 *Доброе утро!*\n\nАктивных обещаний: {len(active)}\n\n{lines}\n\n💡 _{daily_rule()}_"
    await ctx.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

async def evening_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    active = [p for p in data["promises"] if not p["done"]]
    done   = [p for p in data["promises"] if p["done"]]
    msg = (
        f"🌆 *Итог дня*\n\n"
        f"✅ Выполнено: {len(done)}\n"
        f"⏳ Активных: {len(active)}\n\n"
        f"_Каждое выполненное обещание — это кирпич доверия._"
    )
    await ctx.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

# ─── MAIN ───
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("list",   cmd_list))
    app.add_handler(CommandHandler("all",    cmd_all))
    app.add_handler(CommandHandler("done",   cmd_done))
    app.add_handler(CommandHandler("undone", cmd_undone))
    app.add_handler(CommandHandler("add",    cmd_add))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CommandHandler("rule",   cmd_rule))
    app.add_handler(CommandHandler("remind", cmd_remind))
    app.add_handler(CommandHandler("reset",  cmd_reset))

    # Schedule: 9:00 morning, 20:00 evening (UTC+3 = UTC 6:00 and 17:00)
    job_queue = app.job_queue
    job_queue.run_daily(morning_reminder, time=datetime.strptime("06:00", "%H:%M").time())
    job_queue.run_daily(evening_reminder, time=datetime.strptime("17:00", "%H:%M").time())

    print("✅ Бот запущен. Нажми Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
