# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, logging
from datetime import datetime, timezone, timedelta

# ================================================================
#  ТОКЕН — берётся из переменной окружения BOT_TOKEN
#  На Koyeb добавь переменную: BOT_TOKEN = твой_токен
# ================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ================================================================
#  РУХСАТ ЭТИЛГАН ФОЙДАЛАНУВЧИЛАР — Telegram ID ларини киритинг
# ================================================================
ALLOWED_IDS = {
    375749475, 586171498, 105340778, 7371524923
}

# ================================================================
#  ВАҚТ ЗОНАСИ — UTC дан фарқи соатларда (Тошкент = +5)
# ================================================================
TIMEZONE_OFFSET = 5

# ================================================================
#  ТЎЛОв ТУРИНИ ТАНЛАШ ҲУҚУҚИ БОР РОЛ
# ================================================================
TOLOV_TANLASH_ROLI = "Бухгалтер"

# ================================================================
#  База данных — путь берётся из переменной окружения DB_PATH
#  или по умолчанию /data/factory.db (постоянное хранилище Koyeb)
# ================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.environ.get("DB_PATH", os.path.join("/data", "factory.db"))

# Если папка /data не существует — используем локальную папку
if not os.path.exists("/data"):
    DB_PATH = os.path.join(BASE_DIR, "factory.db")

sys.path.insert(0, BASE_DIR)

from database import Database, VALID_ROLES
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler,
    ContextTypes, filters,
)

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.WARNING)
db = Database(DB_PATH)
TZ = timezone(timedelta(hours=TIMEZONE_OFFSET))

def hozir():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M")

def vaqtni_tuzat(utc_str):
    if not utc_str: return "—"
    try:
        dt = datetime.strptime(str(utc_str)[:19], "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc) + timedelta(hours=TIMEZONE_OFFSET)
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return str(utc_str)[:16]

def pul(v):
    try: return "{:,.0f}".format(float(v)).replace(",", " ")
    except: return str(v)

# Харажат турлари (тугмалар)
XARAJAT_TURLARI = [
    "Транспорт",
    "Техник харажатлар",
    "Овқатланиш",
    "Коммунал тўловлар",
    "Маош",
    "Хизмат сафари харажатлари",
    "Хизмат учун",
    "Материаллар",
    "Бошқа",
]

# Даромад манбалари (тугмалар)
DAROMAD_MANBALARI = [
    "Буюртма",
    "Хизмат",
    "Олдиндан тўлов",
    "Қайтим",
    "Бошқа",
]

# ================================================================
# ҲОЛАТЛАР (ConversationHandler states)
# ================================================================
AUTH_CODE = 0
XAR_TUR, XAR_BUYURTMA, XAR_SUMMA, XAR_TOLOV, XAR_IZOH = range(10, 15)
DAR_SUMMA, DAR_TOLOV, DAR_MANBA, DAR_IZOH = range(20, 24)

sessions = {}
tmp = {}

def is_auth(tg_id): return tg_id in sessions
def is_allowed(tg_id): return tg_id in ALLOWED_IDS
def tolov_tanlash_mumkin(tg_id):
    s = sessions.get(tg_id)
    return s is not None and s.get("role") == TOLOV_TANLASH_ROLI

# ================================================================
# КЛАВИАТУРАЛАР
# ================================================================
def kb_moliya():
    return ReplyKeyboardMarkup([
        ["Харажат қўшиш",   "Даромад қўшиш"],
        ["Баланс",           "Харажатлар тарихи"],
        ["Даромадлар тарихи"],
    ], resize_keyboard=True)

def kb_bekor():
    return ReplyKeyboardMarkup([["Бекор қилиш"]], resize_keyboard=True)

def kb_xarajat_turlari():
    rows = [[t] for t in XARAJAT_TURLARI]
    rows.append(["Бекор қилиш"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def kb_daromad_manbalari():
    rows = [[s] for s in DAROMAD_MANBALARI]
    rows.append(["Бекор қилиш"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def kb_tolov_turi():
    return ReplyKeyboardMarkup([["Накд пул", "Ҳисоб"], ["Бекор қилиш"]], resize_keyboard=True)

def kb_otkazib_yubor():
    return ReplyKeyboardMarkup([["Ўтказиб юбориш"], ["Бекор қилиш"]], resize_keyboard=True)

def kb_buyurtmalar(buyurtmalar):
    rows = []
    for o in buyurtmalar[:12]:
        rows.append(["{} | {}".format(o.get("order_code", ""), o.get("client", ""))])
    rows.append(["Ўтказиб юбориш"])
    rows.append(["Бекор қилиш"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ================================================================
# КИРИШ (Авторизация)
# ================================================================
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not is_allowed(tg_id):
        await update.message.reply_text(
            "Кириш тақиқланган.\n"
            "Сизнинг Telegram ID: {}\n\n"
            "Ушбу ID ни администраторга юборинг.".format(tg_id)
        )
        return ConversationHandler.END

    if is_auth(tg_id):
        s = sessions[tg_id]
        await update.message.reply_text(
            "Хуш келибсиз, {}!".format(s["username"]),
            reply_markup=kb_moliya(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Молия бошқарув ботига хуш келибсиз!\n\n"
        "Кириш учун 4 хонали кодингизни киритинг:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return AUTH_CODE

async def handle_auth_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not is_allowed(tg_id):
        await update.message.reply_text("Кириш тақиқланган. Сизнинг ID: {}".format(tg_id))
        return ConversationHandler.END

    code = (update.message.text or "").strip()
    if len(code) != 4 or not code.isdigit():
        await update.message.reply_text("Код 4 та рақамдан иборат бўлиши керак. Қайтадан киритинг:")
        return AUTH_CODE

    user = db.authenticate_user(code)
    if user:
        sessions[tg_id] = {
            "user_id":  user["id"],
            "username": user["username"],
            "role":     user["role"],
        }
        db.log_login_attempt(user["id"], "tg:{}".format(tg_id), True)
        await update.message.reply_text(
            "Хуш келибсиз, {}!\nЛавозим: {}".format(user["username"], user["role"]),
            reply_markup=kb_moliya(),
        )
        return ConversationHandler.END

    db.log_login_attempt(None, "tg:{}".format(tg_id), False)
    await update.message.reply_text("Нотўғри код. Қайтадан уриниб кўринг:")
    return AUTH_CODE

# ================================================================
# БАЛАНС
# ================================================================
async def cmd_balans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        await update.message.reply_text("Кириш учун /start юборинг")
        return
    try:
        bal  = db.get_cash_balance()
        summ = db.get_financial_summary()
        kassa = float(bal.get("cash_amount", 0) or 0)
        hisob = float(bal.get("account_amount", 0) or 0)
        text = (
            "БАЛАНС\n\n"
            "Накд пул:    {} сўм\n"
            "Ҳисоб:    {} сўм\n"
            "Жами:     {} сўм"
        ).format(pul(kassa), pul(hisob), pul(kassa + hisob))
        if summ:
            text += (
                "\n\nДаромад:   {} сўм\n"
                "Харажат:   {} сўм\n"
                "Фойда:     {} сўм"
            ).format(
                pul(summ.get("total_income", 0)),
                pul(summ.get("total_expenses", 0)),
                pul(summ.get("profit", 0)),
            )
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text("Хатолик: {}".format(e))

# ================================================================
# ХАРАЖАТЛАР ТАРИХИ
# ================================================================
async def cmd_xarajatlar_tarixi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return
    try:
        rows = db.get_all_expenses(limit=10)
        if not rows:
            await update.message.reply_text("Ҳали харажатлар йўқ.")
            return
        lines = ["Сўнгги харажатлар:\n"]
        for r in rows:
            tolov = "Накд пул" if r.get("payment_type") == "cash" else "Ҳисоб"
            kim   = r.get("username") or "—"
            buyur = r.get("order_ref") or "—"
            vaqt  = vaqtni_tuzat(r.get("created_at", ""))
            lines.append(
                "{}\n"
                "  Тур: {} | {} сўм | {}\n"
                "  Буюртма: {} | Ким: {}".format(
                    vaqt,
                    r.get("expense_type", "—"),
                    pul(r.get("amount", 0)),
                    tolov, buyur, kim,
                )
            )
        await update.message.reply_text("\n\n".join(lines))
    except Exception as e:
        await update.message.reply_text("Хатолик: {}".format(e))

# ================================================================
# ДАРОМАДЛАР ТАРИХИ
# ================================================================
async def cmd_daromadlar_tarixi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return
    try:
        rows = db.get_all_income(limit=10)
        if not rows:
            await update.message.reply_text("Ҳали даромадлар йўқ.")
            return
        lines = ["Сўнгги даромадлар:\n"]
        for r in rows:
            tolov = "Накд пул" if r.get("payment_type") == "cash" else "Ҳисоб"
            kim   = r.get("username") or "—"
            vaqt  = vaqtni_tuzat(r.get("created_at", ""))
            lines.append(
                "{}\n"
                "  Манба: {} | {} сўм | {}\n"
                "  Ким: {}".format(
                    vaqt,
                    r.get("source", "—"),
                    pul(r.get("amount", 0)),
                    tolov, kim,
                )
            )
        await update.message.reply_text("\n\n".join(lines))
    except Exception as e:
        await update.message.reply_text("Хатолик: {}".format(e))

# ================================================================
# ХАРАЖАТ ҚЎШИШ — диалог
# ================================================================
async def xar_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not is_auth(tg_id):
        await update.message.reply_text("Кириш учун /start юборинг")
        return ConversationHandler.END
    tmp[tg_id] = {}
    await update.message.reply_text(
        "Янги харажат\n\n"
        "1-қадам / 5 — Харажат турини танланг:",
        reply_markup=kb_xarajat_turlari(),
    )
    return XAR_TUR

async def xar_get_tur(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    text = (update.message.text or "").strip()
    if text == "Бекор қилиш": return await bekor_qilish(update, ctx)
    tmp[tg_id]["expense_type"] = text

    try:
        buyurtmalar = db.get_orders(limit=20, status="active")
    except:
        buyurtmalar = []
    tmp[tg_id]["_buyurtmalar"] = buyurtmalar

    if buyurtmalar:
        await update.message.reply_text(
            "2-қадам / 5 — Буюртмани танланг ёки ўтказиб юборинг:",
            reply_markup=kb_buyurtmalar(buyurtmalar),
        )
    else:
        tmp[tg_id]["order_ref"] = None
        await update.message.reply_text(
            "Фаол буюртмалар йўқ.\n\n"
            "3-қадам / 5 — Суммани киритинг (сўмда):",
            reply_markup=kb_bekor(),
        )
        return XAR_SUMMA

    return XAR_BUYURTMA

async def xar_get_buyurtma(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    text = (update.message.text or "").strip()
    if text == "Бекор қилиш": return await bekor_qilish(update, ctx)

    if text == "Ўтказиб юбориш":
        tmp[tg_id]["order_ref"] = None
    else:
        order_code = text.split("|")[0].strip()
        tmp[tg_id]["order_ref"] = order_code

    await update.message.reply_text(
        "3-қадам / 5 — Суммани киритинг (сўмда):",
        reply_markup=kb_bekor(),
    )
    return XAR_SUMMA

async def xar_get_summa(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    text = (update.message.text or "").strip()
    if text == "Бекор қилиш": return await bekor_qilish(update, ctx)
    try:
        summa = float(text.replace(",", ".").replace(" ", "").replace("\u00a0", ""))
        if summa <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("Мусбат сон киритинг:")
        return XAR_SUMMA
    tmp[tg_id]["amount"] = summa

    if tolov_tanlash_mumkin(tg_id):
        await update.message.reply_text(
            "4-қадам / 5 — Тўлов турини танланг:",
            reply_markup=kb_tolov_turi(),
        )
        return XAR_TOLOV
    else:
        tmp[tg_id]["payment_type"] = "cash"
        await update.message.reply_text(
            "5-қадам / 5 — Изоҳ киритинг (ёки ўтказиб юборинг):",
            reply_markup=kb_otkazib_yubor(),
        )
        return XAR_IZOH

async def xar_get_tolov(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    text = (update.message.text or "").strip()
    if text == "Бекор қилиш": return await bekor_qilish(update, ctx)
    if text == "Накд пул":   tmp[tg_id]["payment_type"] = "cash"
    elif text == "Ҳисоб": tmp[tg_id]["payment_type"] = "account"
    else:
        await update.message.reply_text("Накд пул ёки Ҳисоб ни танланг:")
        return XAR_TOLOV
    await update.message.reply_text(
        "5-қадам / 5 — Изоҳ киритинг (ёки ўтказиб юборинг):",
        reply_markup=kb_otkazib_yubor(),
    )
    return XAR_IZOH

async def xar_get_izoh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    s = sessions[tg_id]
    text = (update.message.text or "").strip()
    if text == "Бекор қилиш": return await bekor_qilish(update, ctx)
    izoh = None if text == "Ўтказиб юбориш" else text
    d = tmp.pop(tg_id, {})
    d.pop("_buyurtmalar", None)

    try:
        eid = db.add_expense(
            expense_type=d["expense_type"],
            amount=d["amount"],
            payment_type=d["payment_type"],
            order_ref=d.get("order_ref"),
            comment=izoh,
            user_id=s["user_id"],
        )
        bal = db.get_cash_balance()
        tolov_label = "Накд пул" if d["payment_type"] == "cash" else "Ҳисоб"
        buyurtma_label = d.get("order_ref") or "—"
        await update.message.reply_text(
            "Харажат қўшилди!\n\n"
            "ID:        {}\n"
            "Вақт:      {}\n"
            "Тур:       {}\n"
            "Буюртма:   {}\n"
            "Сумма:     {} сўм\n"
            "Тўлов:     {}\n"
            "Изоҳ:      {}\n"
            "Қўшди:     {}\n\n"
            "Накд пул: {} | Ҳисоб: {}".format(
                eid, hozir(), d["expense_type"], buyurtma_label,
                pul(d["amount"]), tolov_label, izoh or "—", s["username"],
                pul(bal.get("cash_amount", 0)), pul(bal.get("account_amount", 0)),
            ),
            reply_markup=kb_moliya(),
        )
    except Exception as e:
        await update.message.reply_text("Хатолик: {}".format(e), reply_markup=kb_moliya())
    return ConversationHandler.END

# ================================================================
# ДАРОМАД ҚЎШИШ — диалог
# ================================================================
async def dar_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not is_auth(tg_id):
        await update.message.reply_text("Кириш учун /start юборинг")
        return ConversationHandler.END
    tmp[tg_id] = {}
    await update.message.reply_text(
        "Янги даромад\n\n"
        "1-қадам / 4 — Суммани киритинг (сўмда):",
        reply_markup=kb_bekor(),
    )
    return DAR_SUMMA

async def dar_get_summa(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    text = (update.message.text or "").strip()
    if text == "Бекор қилиш": return await bekor_qilish(update, ctx)
    try:
        summa = float(text.replace(",", ".").replace(" ", "").replace("\u00a0", ""))
        if summa <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("Мусбат сон киритинг:")
        return DAR_SUMMA
    tmp[tg_id]["amount"] = summa

    if tolov_tanlash_mumkin(tg_id):
        await update.message.reply_text(
            "2-қадам / 4 — Тўлов турини танланг:",
            reply_markup=kb_tolov_turi(),
        )
        return DAR_TOLOV
    else:
        tmp[tg_id]["payment_type"] = "cash"
        await update.message.reply_text(
            "3-қадам / 4 — Даромад манбасини танланг:",
            reply_markup=kb_daromad_manbalari(),
        )
        return DAR_MANBA

async def dar_get_tolov(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    text = (update.message.text or "").strip()
    if text == "Бекор қилиш": return await bekor_qilish(update, ctx)
    if text == "Накд пул":   tmp[tg_id]["payment_type"] = "cash"
    elif text == "Ҳисоб": tmp[tg_id]["payment_type"] = "account"
    else:
        await update.message.reply_text("Накд пул ёки Ҳисоб ни танланг:")
        return DAR_TOLOV
    await update.message.reply_text(
        "3-қадам / 4 — Даромад манбасини танланг:",
        reply_markup=kb_daromad_manbalari(),
    )
    return DAR_MANBA

async def dar_get_manba(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    text = (update.message.text or "").strip()
    if text == "Бекор қилиш": return await bekor_qilish(update, ctx)
    tmp[tg_id]["source"] = text
    await update.message.reply_text(
        "4-қадам / 4 — Изоҳ киритинг (ёки ўтказиб юборинг):",
        reply_markup=kb_otkazib_yubor(),
    )
    return DAR_IZOH

async def dar_get_izoh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    s = sessions[tg_id]
    text = (update.message.text or "").strip()
    if text == "Бекор қилиш": return await bekor_qilish(update, ctx)
    izoh = None if text == "Ўтказиб юбориш" else text
    d = tmp.pop(tg_id, {})
    try:
        iid = db.add_income(
            amount=d["amount"],
            payment_type=d["payment_type"],
            source=d["source"],
            comment=izoh,
            user_id=s["user_id"],
        )
        bal = db.get_cash_balance()
        tolov_label = "Накд пул" if d["payment_type"] == "cash" else "Ҳисоб"
        await update.message.reply_text(
            "Даромад қўшилди!\n\n"
            "ID:        {}\n"
            "Вақт:      {}\n"
            "Манба:     {}\n"
            "Сумма:     {} сўм\n"
            "Тўлов:     {}\n"
            "Изоҳ:      {}\n"
            "Қўшди:     {}\n\n"
            "Касса: {} | Ҳисоб: {}".format(
                iid, hozir(), d["source"], pul(d["amount"]),
                tolov_label, izoh or "—", s["username"],
                pul(bal.get("cash_amount", 0)), pul(bal.get("account_amount", 0)),
            ),
            reply_markup=kb_moliya(),
        )
    except Exception as e:
        await update.message.reply_text("Хатолик: {}".format(e), reply_markup=kb_moliya())
    return ConversationHandler.END

# ================================================================
# АСОСИЙ МАТН ИШЛОВ БЕРУВЧИ
# ================================================================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    text  = (update.message.text or "").strip()

    if not is_allowed(tg_id):
        await update.message.reply_text(
            "Кириш тақиқланган. Сизнинг Telegram ID: {}".format(tg_id))
        return

    if not is_auth(tg_id):
        await update.message.reply_text("Кириш учун /start юборинг")
        return

    if   text == "Баланс":               await cmd_balans(update, ctx)
    elif text == "Харажатлар тарихи":    await cmd_xarajatlar_tarixi(update, ctx)
    elif text == "Даромадлар тарихи":    await cmd_daromadlar_tarixi(update, ctx)

async def cmd_myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    await update.message.reply_text(
        "Сизнинг Telegram ID: {}\n"
        "Исм: {}".format(tg_id, update.effective_user.full_name)
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Буйруқлар:\n\n"
        "/start — Тизимга кириш\n"
        "/myid  — Telegram ID ни билиш\n"
        "/help  — Ёрдам"
    )

async def bekor_qilish(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    tmp.pop(tg_id, None)
    await update.message.reply_text("Бекор қилинди.", reply_markup=kb_moliya())
    return ConversationHandler.END

# ================================================================
# ИШГА ТУШИРИШ
# ================================================================
def main():
    if not BOT_TOKEN:
        print("\nХАТО: BOT_TOKEN переменная окружения не задана!\n")
        print("На Koyeb добавьте переменную окружения BOT_TOKEN=ваш_токен\n")
        sys.exit(1)

    print("Бот ишга тушмоқда...")
    print("База данных: " + DB_PATH)
    print("Маълумотлар базаси: " + ("топилди OK" if os.path.exists(DB_PATH) else "янги яратилади: " + DB_PATH))
    print("Вақт зонаси: UTC+{}".format(TIMEZONE_OFFSET))
    print("Рухсат этилган фойдаланувчилар: {}".format(len(ALLOWED_IDS)))

    app = Application.builder().token(BOT_TOKEN).build()

    auth_conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={AUTH_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_auth_code)]},
        fallbacks=[CommandHandler("start", cmd_start)],
    )

    xarajat_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Харажат қўшиш$"), xar_start)],
        states={
            XAR_TUR:      [MessageHandler(filters.TEXT & ~filters.COMMAND, xar_get_tur)],
            XAR_BUYURTMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, xar_get_buyurtma)],
            XAR_SUMMA:    [MessageHandler(filters.TEXT & ~filters.COMMAND, xar_get_summa)],
            XAR_TOLOV:    [MessageHandler(filters.TEXT & ~filters.COMMAND, xar_get_tolov)],
            XAR_IZOH:     [MessageHandler(filters.TEXT & ~filters.COMMAND, xar_get_izoh)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
    )

    daromad_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Даромад қўшиш$"), dar_start)],
        states={
            DAR_SUMMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, dar_get_summa)],
            DAR_TOLOV: [MessageHandler(filters.TEXT & ~filters.COMMAND, dar_get_tolov)],
            DAR_MANBA: [MessageHandler(filters.TEXT & ~filters.COMMAND, dar_get_manba)],
            DAR_IZOH:  [MessageHandler(filters.TEXT & ~filters.COMMAND, dar_get_izoh)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
    )

    app.add_handler(auth_conv)
    app.add_handler(xarajat_conv)
    app.add_handler(daromad_conv)
    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("\nБот ишга тушди! Telegramда /start юборинг.")
    print("Тўхтатиш учун: Ctrl+C\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
