import os
import json
import asyncio
import threading
from datetime import datetime, time as dtime
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ─── KEEP-ALIVE ───
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, format, *args):
        pass

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), KeepAlive)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()

# ─── CONFIG ───
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8742841723:AAF20S6vnWpN2B3RjbBdEPrqTDFWhh8B1Fk")
CHAT_ID   = int(os.environ.get("CHAT_ID", "814959844"))
DATA_FILE = "promises.json"

DEFAULT_PROMISES = [
    {"id": 1, "text": "Отправить доставку",                               "type": "once",    "done": False},
    {"id": 2, "text": "Не обзывать себя",                                 "type": "regular", "done": False},
    {"id": 3, "text": "Платить за курсы по истории",                      "type": "regular", "done": False},
    {"id": 4, "text": "Купить всё для волос",                             "type": "once",    "done": False},
    {"id": 5, "text": "Помочь с Apple Pay",                               "type": "meeting", "done": False},
    {"id": 6, "text": "Сходить за кремом",                                "type": "meeting", "done": False},
    {"id": 7, "text": "Когда она расстроена — не молчать, присутствовать","type": "regular", "done": False},
    {"id": 8, "text": "Быть внимательным к мелочам",                      "type": "regular", "done": False},
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

def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    data = {"promises": [p.copy() for p in DEFAULT_PROMISES], "next_id": 9}
    save(data)
    return data

def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
            lines.append(f"• {p['text']} ✓")
    lines.append(f"\n_Выполнено: {len(done)}/{len(promises)}_")
    return "\n".join(lines)

def daily_rule():
    return RULES[datetime.now().day % len(RULES)]

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = ("👋 *Трекер обещаний запущен*\n\n"
            "/list — активные обещания\n/all — все\n/done 3 — выполнено\n"
            "/undone 3 — вернуть\n/add Текст — добавить\n/delete 3 — удалить\n"
            "/rule — правило дня\n/remind — напомнить\n/reset — сбросить\n")
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_list(load()["promises"]), parse_mode="Markdown")

async def cmd_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_list(load()["promises"], show_done=True), parse_mode="Markdown")

async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("Укажи номер: /done 3"); return
    pid = int(ctx.args[0])
    data = load()
    p = next((x for x in data["promises"] if x["id"] == pid), None)
    if not p:
        await update.message.reply_text(f"#{pid} не найдено"); return
    p["done"] = True
    p["done_at"] = datetime.now().strftime("%d.%m.%Y")
    save(data)
    active = len([x for x in data["promises"] if not x["done"]])
    await update.message.reply_text(f"✅ *{p['text']}*\n\nОсталось: {active}", parse_mode="Markdown")

async def cmd_undone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("Укажи номер: /undone 3"); return
    pid = int(ctx.args[0])
    data = load()
    p = next((x for x in data["promises"] if x["id"] == pid), None)
    if not p:
        await update.message.reply_text(f"#{pid} не найдено"); return
    p["done"] = False; p.pop("done_at", None); save(data)
    await update.message.reply_text(f"↩️ Возвращено: *{p['text']}*", parse_mode="Markdown")

async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = " ".join(ctx.args).strip()
    if not text:
        await update.message.reply_text("Напиши: /add Текст"); return
    data = load()
    data["promises"].append({"id": data["next_id"], "text": text, "type": "once", "done": False,
                              "created_at": datetime.now().strftime("%d.%m.%Y")})
    data["next_id"] += 1; save(data)
    await update.message.reply_text(f"➕ *{text}*\n\n_Записано — значит существует._", parse_mode="Markdown")

async def cmd_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("Укажи номер: /delete 3"); return
    pid = int(ctx.args[0])
    data = load()
    before = len(data["promises"])
    data["promises"] = [x for x in data["promises"] if x["id"] != pid]
    if len(data["promises"]) == before:
        await update.message.reply_text(f"#{pid} не найдено"); return
    save(data)
    await update.message.reply_text(f"🗑 #{pid} удалено")

async def cmd_rule(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"💡 *Правило дня:*\n\n{daily_rule()}", parse_mode="Markdown")

async def cmd_remind(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_list(load()["promises"]), parse_mode="Markdown")

async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    save({"promises": [p.copy() for p in DEFAULT_PROMISES], "next_id": 9})
    await update.message.reply_text("♻️ Сброшено к началу")

async def morning_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    active = [p for p in data["promises"] if not p["done"]]
    if not active:
        msg = "🌅 Доброе утро!\n\n✨ Все обещания выполнены!"
    else:
        lines = "\n".join(f"• [{p['id']}] {p['text']}" for p in active)
        msg = f"🌅 *Доброе утро!*\n\nАктивных: {len(active)}\n\n{lines}\n\n💡 _{daily_rule()}_"
    await ctx.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

async def evening_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    active = [p for p in data["promises"] if not p["done"]]
    done = [p for p in data["promises"] if p["done"]]
    msg = (f"🌆 *Итог дня*\n\n✅ Выполнено: {len(done)}\n⏳ Активных: {len(active)}\n\n"
           f"_Каждое выполненное обещание — это кирпич доверия._")
    await ctx.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

async def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
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
    app.job_queue.run_daily(morning_reminder, time=dtime(6, 0))
    app.job_queue.run_daily(evening_reminder, time=dtime(17, 0))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    print("✅ Бот запущен.")
    # держим бота живым вечно
    await asyncio.Event().wait()

if __name__ == "__main__":
    keep_alive()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot())
