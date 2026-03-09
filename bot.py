import os
import json
import asyncio
import threading
import urllib.request
import urllib.error
from datetime import datetime, time as dtime
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

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
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "8742841723:AAE78Bt3viP5Ii6E4_lro5kT19IPrFLxy7A")
CHAT_ID      = int(os.environ.get("CHAT_ID", "814959844"))
JSONBIN_KEY  = os.environ.get("JSONBIN_KEY", "$2a$10$l6b/WIWg9SANGQPu2qGpuufBI1KvSUToJzUieUYVglVNbbMBthyja")
JSONBIN_BIN  = os.environ.get("JSONBIN_BIN", "69af3127d0ea881f4001c5df")
QUIZ_INTERVAL = 7 * 60

DEFAULT_PROMISES = [
    {"id": 1,  "text": "Отправить доставку",                                "type": "once",    "done": False},
    {"id": 2,  "text": "Не обзывать себя",                                  "type": "regular", "done": False},
    {"id": 3,  "text": "Платить за курсы по истории",                       "type": "regular", "done": False},
    {"id": 4,  "text": "Купить всё для волос",                              "type": "once",    "done": False},
    {"id": 5,  "text": "Помочь с Apple Pay",                                "type": "meeting", "done": False},
    {"id": 6,  "text": "Сходить за кремом",                                 "type": "meeting", "done": False},
    {"id": 7,  "text": "Когда она расстроена — не молчать, присутствовать", "type": "regular", "done": False},
    {"id": 8,  "text": "Быть внимательным к мелочам",                      "type": "regular", "done": False},
    {"id": 9,  "text": "Пойти в зал",                                       "type": "regular", "done": False},
    {"id": 10, "text": "Бросить курить",                                    "type": "regular", "done": False},
    {"id": 11, "text": "Режим и сбалансированно кушать",                    "type": "regular", "done": False},
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
    "Её кокон — не наказание. Это её способ восстановиться.",
    "Давление во время её молчания только углубляет дистанцию.",
    "Один сигнал присутствия — и тишина. Этого достаточно.",
    "Она возвращается каждый раз. Это и есть ответ на твой главный вопрос.",
    "Не объявляй об изменениях — просто меняйся. Она заметит сама.",
    "Счёт любви полный. Сейчас важен счёт надёжности.",
    "Претензия — это не атака. Это информация от взрослого человека.",
    "Выполненное обещание весит больше любых слов о любви.",
    "Три года вместе на расстоянии — это не случайность.",
    "Когда хочется «починить» прямо сейчас — спроси себя: для кого это?",
    "Тихое действие без объявления — самый громкий язык для неё.",
    "Заметил паттерн — уже половина победы над ним.",
]

# ─── JSONBIN STORAGE ───
def _jsonbin_headers(write=False):
    h = {"X-Master-Key": JSONBIN_KEY, "Content-Type": "application/json"}
    if not write:
        h["X-Bin-Meta"] = "false"
    return h

def cloud_load():
    if not JSONBIN_KEY or not JSONBIN_BIN:
        return _default_data()
    try:
        req = urllib.request.Request(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN}/latest",
            headers=_jsonbin_headers()
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"cloud_load error: {e}")
        return _default_data()

def cloud_save(data):
    if not JSONBIN_KEY or not JSONBIN_BIN:
        return
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN}",
            data=body,
            headers=_jsonbin_headers(write=True),
            method="PUT"
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"cloud_save error: {e}")

def _default_data():
    return {
        "promises": [p.copy() for p in DEFAULT_PROMISES],
        "next_id": 12,
        "quiz": {"active": False, "remaining": []}
    }

def load():
    data = cloud_load()
    if "promises" not in data:
        data = _default_data()
    if "quiz" not in data:
        data["quiz"] = {"active": False, "remaining": []}
    if "next_id" not in data:
        data["next_id"] = max((p["id"] for p in data["promises"]), default=0) + 1
    return data

def save(data):
    cloud_save(data)

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
            lines.append(f"• {p['text']} ✓")
    lines.append(f"\n_Выполнено: {len(done)}/{len(promises)}_")
    return "\n".join(lines)

def daily_rule():
    return RULES[datetime.now().timetuple().tm_yday % len(RULES)]

def normalize(text):
    return text.lower().strip().replace("ё", "е")

def check_match(user_text, promise_text):
    user = normalize(user_text)
    target = normalize(promise_text)
    words = [w for w in target.split() if len(w) > 3]
    if not words:
        return user in target or target in user
    matched = sum(1 for w in words if w in user)
    return matched >= max(1, len(words) * 0.6)

# ─── QUIZ ───
async def start_quiz(bot, job_queue):
    data = load()
    all_texts = [p["text"] for p in data["promises"]]
    data["quiz"] = {"active": True, "remaining": all_texts}
    save(data)
    # отменяем старый пинг если есть
    for job in job_queue.get_jobs_by_name("quiz_ping"):
        job.schedule_removal()
    await bot.send_message(
        chat_id=CHAT_ID,
        text=(f"📝 *Квиз запущен!*\n\n"
              f"Назови все {len(all_texts)} обещаний — по одному или все сразу.\n"
              f"Пока не назовёшь все — буду напоминать каждые 7 минут.\n\n"
              f"_Просто пиши в чат — команды не нужны_"),
        parse_mode="Markdown"
    )
    job_queue.run_once(quiz_ping, QUIZ_INTERVAL, name="quiz_ping")

async def quiz_ping(ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    q = data.get("quiz", {})
    if not q.get("active") or not q.get("remaining"):
        return
    remaining = q["remaining"]
    lines = "\n".join(f"• {p}" for p in remaining)
    await ctx.bot.send_message(
        chat_id=CHAT_ID,
        text=(f"⏰ *Ещё не всё названо!*\n\n"
              f"Осталось {len(remaining)}:\n{lines}\n\n"
              f"_Просто напиши их в чат_"),
        parse_mode="Markdown"
    )
    ctx.job_queue.run_once(quiz_ping, QUIZ_INTERVAL, name="quiz_ping")

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    q = data.get("quiz", {})
    if not q.get("active") or not q.get("remaining"):
        return
    user_text = update.message.text
    remaining = q["remaining"]
    matched = []
    still = []
    for promise in remaining:
        if check_match(user_text, promise):
            matched.append(promise)
        else:
            still.append(promise)
    if not matched:
        return
    data["quiz"]["remaining"] = still
    if not still:
        data["quiz"]["active"] = False
        save(data)
        for job in ctx.job_queue.get_jobs_by_name("quiz_ping"):
            job.schedule_removal()
        lines = "\n".join(f"✅ {p}" for p in matched)
        await update.message.reply_text(
            f"{lines}\n\n🎉 *Отлично! Все обещания названы!*\n\n_Ты молодец. До следующего раза._",
            parse_mode="Markdown"
        )
    else:
        save(data)
        lines = "\n".join(f"✅ {p}" for p in matched)
        await update.message.reply_text(
            f"{lines}\n\n_Осталось: {len(still)}_",
            parse_mode="Markdown"
        )

# ─── COMMANDS ───
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Трекер обещаний запущен*\n\n"
        "/list — активные обещания\n/all — все\n"
        "/done 3 — выполнено\n/undone 3 — вернуть\n"
        "/add o|r|m Текст — добавить\n/delete 3 — удалить\n"
        "/rule — правило дня\n/remind — список\n"
        "/quiz — начать квиз\n/reset — сбросить",
        parse_mode="Markdown"
    )

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
    if not ctx.args:
        await update.message.reply_text(
            "Напиши:\n"
            "/add o Купить крем — разовое\n"
            "/add r Не обзывать себя — регулярное\n"
            "/add m Помочь с Apple Pay — при встрече"
        ); return
    TYPE_MAP = {"r": "regular", "o": "once", "m": "meeting"}
    TYPE_LABEL = {"regular": "регулярное", "once": "разовое", "meeting": "при встрече"}
    if ctx.args[0].lower() in TYPE_MAP:
        ptype = TYPE_MAP[ctx.args[0].lower()]
        text = " ".join(ctx.args[1:]).strip()
    else:
        ptype = "once"
        text = " ".join(ctx.args).strip()
    if not text:
        await update.message.reply_text("Укажи текст обещания после типа"); return
    data = load()
    data["promises"].append({"id": data["next_id"], "text": text, "type": ptype, "done": False,
                              "created_at": datetime.now().strftime("%d.%m.%Y")})
    data["next_id"] += 1
    save(data)
    await update.message.reply_text(
        f"➕ *{text}*  _({TYPE_LABEL[ptype]})_\n\n_Записано — значит существует._",
        parse_mode="Markdown"
    )

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

async def cmd_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await start_quiz(ctx.bot, ctx.job_queue)

async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    save(_default_data())
    await update.message.reply_text("♻️ Сброшено к началу")

# ─── SCHEDULED ───
async def morning_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    active = [p for p in data["promises"] if not p["done"]]
    rule = daily_rule()
    if not active:
        msg = f"🌅 *Доброе утро!*\n\n✨ Все обещания выполнены!\n\n💡 _{rule}_"
    else:
        lines = "\n".join(f"• [{p['id']}] {p['text']}" for p in active)
        msg = f"🌅 *Доброе утро!*\n\nАктивных: {len(active)}\n\n{lines}\n\n💡 _{rule}_"
    await ctx.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    await start_quiz(ctx.bot, ctx.job_queue)

async def evening_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    active = [p for p in data["promises"] if not p["done"]]
    done   = [p for p in data["promises"] if p["done"]]
    rule = daily_rule()
    if not active:
        promises_msg = "✨ Все обещания выполнены!"
    else:
        lines = "\n".join(f"• [{p['id']}] {p['text']}" for p in active)
        promises_msg = f"⏳ Активных: {len(active)}\n\n{lines}"
    msg = f"🌆 *Итог дня*\n\n✅ Выполнено: {len(done)}\n{promises_msg}\n\n💡 _{rule}_"
    await ctx.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    await start_quiz(ctx.bot, ctx.job_queue)

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
    app.add_handler(CommandHandler("quiz",   cmd_quiz))
    app.add_handler(CommandHandler("reset",  cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.job_queue.run_daily(morning_reminder, time=dtime(6, 0))
    app.job_queue.run_daily(evening_reminder, time=dtime(17, 0))
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    print("✅ Бот запущен.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    keep_alive()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot())
