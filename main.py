# -*- coding: utf-8 -*-

import asyncio
import sqlite3
import secrets
import re
from datetime import datetime

# ============================================================
# تنظیمات
# ============================================================

TOKEN = "70194088:-sfga7s3p0MXcI4XDGDbU9i7XvCExXMGm3s"

DB_NAME = "fbi_chat.db"

# ============================================================
# دیتابیس
# ============================================================

db = sqlite3.connect(DB_NAME, check_same_thread=False)
db.row_factory = sqlite3.Row

db.executescript("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    city TEXT NOT NULL,
    gender TEXT NOT NULL,
    code TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    user_id TEXT PRIMARY KEY,
    partner_id TEXT,
    active INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS blocks (
    user_id TEXT,
    blocked_id TEXT,
    PRIMARY KEY(user_id, blocked_id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter TEXT,
    target TEXT,
    reason TEXT,
    created_at TEXT
);
""")

db.commit()

states = {}


# ============================================================
# توابع دیتابیس
# ============================================================

def get_user(user_id):
    return db.execute(
        "SELECT * FROM users WHERE user_id=?",
        (str(user_id),)
    ).fetchone()


def save_user(user_id, name, age, city, gender):

    code = secrets.token_hex(4).upper()

    db.execute(
        """
        INSERT OR REPLACE INTO users
        (user_id,name,age,city,gender,code,created_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            str(user_id),
            name,
            age,
            city,
            gender,
            code,
            datetime.now().isoformat()
        )
    )

    db.commit()


def get_partner(user_id):

    row = db.execute(
        """
        SELECT partner_id
        FROM sessions
        WHERE user_id=? AND active=1
        """,
        (str(user_id),)
    ).fetchone()

    if row:
        return row["partner_id"]

    return None


def set_session(user1, user2):

    db.execute(
        """
        INSERT OR REPLACE INTO sessions
        (user_id,partner_id,active)
        VALUES (?,?,1)
        """,
        (str(user1), str(user2))
    )

    db.execute(
        """
        INSERT OR REPLACE INTO sessions
        (user_id,partner_id,active)
        VALUES (?,?,1)
        """,
        (str(user2), str(user1))
    )

    db.commit()


def end_session(user_id):

    partner = get_partner(user_id)

    db.execute(
        """
        UPDATE sessions
        SET active=0, partner_id=NULL
        WHERE user_id=?
        """,
        (str(user_id),)
    )

    if partner:

        db.execute(
            """
            UPDATE sessions
            SET active=0, partner_id=NULL
            WHERE user_id=?
            """,
            (str(partner),)
        )

    db.commit()

    return partner


def is_blocked(user1, user2):

    result = db.execute(
        """
        SELECT 1
        FROM blocks
        WHERE user_id=? AND blocked_id=?
        """,
        (str(user1), str(user2))
    ).fetchone()

    return result is not None


# ============================================================
# فیلتر اطلاعات تماس
# ============================================================

BLOCK_PATTERNS = [

    r"https?://",

    r"www\.",

    r"t\.me/",

    r"rubika\.ir/",

    r"splus\.ir/",

    r"@\w{3,}",

    r"\b09\d{9}\b",

    r"\b(?:\+98|0098)9\d{9}\b",
]


def contains_contact_info(text):

    text = text.lower()

    for pattern in BLOCK_PATTERNS:

        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


# ============================================================
# پیدا کردن کاربر
# ============================================================

def find_match(user_id):

    me = get_user(user_id)

    if not me:
        return None

    users = db.execute(
        """
        SELECT *
        FROM users
        WHERE user_id != ?
        AND ABS(age - ?) <= 2
        """,
        (
            str(user_id),
            me["age"]
        )
    ).fetchall()

    for user in users:

        if is_blocked(user_id, user["user_id"]):
            continue

        if is_blocked(user["user_id"], user_id):
            continue

        if get_partner(user["user_id"]):
            continue

        return user

    return None


# ============================================================
# پروفایل
# ============================================================

def profile(user_id):

    user = get_user(user_id)

    if not user:
        return "پروفایل پیدا نشد."

    return (
        "👤 پروفایل کاربر\n\n"
        f"نام: {user['name']}\n"
        f"سن: {user['age']}\n"
        f"شهر: {user['city']}\n"
        f"جنسیت: {user['gender']}"
    )


# ============================================================
# منوی اصلی
# ============================================================

MAIN_MENU = """
🔎 اتصال به هم‌شهری
👩 اتصال دختر
👨 اتصال پسر

✏️ تغییر ویژگی
🔗 لینک من
"""


CHAT_MENU = """
👤 مشاهده پروفایل
⚠️ گزارش
🔚 پایان چت
"""


# ============================================================
# پردازش پیام
# ============================================================

async def process_message(user_id, text):

    user_id = str(user_id)

    text = (text or "").strip()

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    if text in ("/start", "شروع"):

        user = get_user(user_id)

        if user:

            return (
                "درود 👋\n\n"
                "به FBI Chat خوش آمدید.\n\n"
                "از منوی زیر انتخاب کنید:\n\n"
                + MAIN_MENU
            )

        states[user_id] = {
            "step": "name"
        }

        return (
            "درود 👋\n\n"
            "به FBI Chat خوش آمدید.\n\n"
            "برای شروع یک نام مستعار وارد کنید:"
        )

    # --------------------------------------------------------
    # ثبت نام
    # --------------------------------------------------------

    state = states.get(user_id)

    if state:

        # نام

        if state["step"] == "name":

            if len(text) < 2 or len(text) > 30:

                return "نام باید بین ۲ تا ۳۰ کاراکتر باشد."

            state["name"] = text

            state["step"] = "age"

            return "سن خود را وارد کنید (۱۳ تا ۱۷):"

        # سن

        if state["step"] == "age":

            if not text.isdigit():

                return "سن باید عدد باشد."

            age = int(text)

            if age < 13 or age > 17:

                return "لطفاً سن بین ۱۳ تا ۱۷ وارد کنید."

            state["age"] = age

            state["step"] = "city"

            return "شهر خود را وارد کنید:"

        # شهر

        if state["step"] == "city":

            if len(text) < 2:

                return "نام شهر معتبر وارد کنید."

            state["city"] = text

            state["step"] = "gender"

            return (
                "جنسیت خود را انتخاب کنید:\n\n"
                "دختر\n"
                "پسر\n"
                "ترجیح می‌دهم نگویم"
            )

        # جنسیت

        if state["step"] == "gender":

            genders = {
                "دختر": "دختر",
                "پسر": "پسر",
                "ترجیح می‌دهم نگویم": "نامشخص"
            }

            if text not in genders:

                return (
                    "یکی از گزینه‌های زیر را انتخاب کنید:\n\n"
                    "دختر\n"
                    "پسر\n"
                    "ترجیح می‌دهم نگویم"
                )

            state["gender"] = genders[text]

            save_user(
                user_id,
                state["name"],
                state["age"],
                state["city"],
                state["gender"]
            )

            states.pop(user_id, None)

            return (
                "✅ پروفایل شما ساخته شد.\n\n"
                "حالا می‌توانید شروع کنید:\n\n"
                + MAIN_MENU
            )

    # --------------------------------------------------------
    # پایان چت
    # --------------------------------------------------------

    if text in ("پایان چت", "پایان"):

        partner = end_session(user_id)

        if partner:

            return "🔚 چت پایان یافت."

        return "شما در حال حاضر چتی ندارید."

    # --------------------------------------------------------
    # مشاهده پروفایل
    # --------------------------------------------------------

    if text in ("مشاهده پروفایل", "پروفایل"):

        partner = get_partner(user_id)

        if not partner:

            return "شما در حال حاضر در چت نیستید."

        return profile(partner)

    # --------------------------------------------------------
    # گزارش
    # --------------------------------------------------------

    if text in ("گزارش", "گزارش کاربر"):

        partner = get_partner(user_id)

        if not partner:

            return "شما در حال حاضر در چت نیستید."

        db.execute(
            """
            INSERT INTO reports
            (reporter,target,reason,created_at)
            VALUES (?,?,?,?)
            """,
            (
                user_id,
                partner,
                "گزارش کاربر",
                datetime.now().isoformat()
            )
        )

        db.commit()

        end_session(user_id)

        return (
            "⚠️ گزارش ثبت شد.\n\n"
            "چت نیز پایان داده شد."
        )

    # --------------------------------------------------------
    # تغییر ویژگی
    # --------------------------------------------------------

    if text == "تغییر ویژگی":

        states[user_id] = {
            "step": "name"
        }

        return "نام مستعار جدید خود را وارد کنید:"

    # --------------------------------------------------------
    # لینک من
    # --------------------------------------------------------

    if text == "لینک من":

        user = get_user(user_id)

        if not user:

            return "ابتدا /start را بزنید."

        return (
            "🔗 کد اختصاصی شما:\n\n"
            f"{user['code']}\n\n"
            "این کد را فقط داخل خود بات استفاده کنید."
        )

    # --------------------------------------------------------
    # اتصال
    # --------------------------------------------------------

    if text.startswith("اتصال"):

        me = get_user(user_id)

        if not me:

            return "ابتدا /start را بزنید."

        if get_partner(user_id):

            return "شما همین الان در یک چت هستید."

        partner = find_match(user_id)

        if not partner:

            return (
                "🔎 فعلاً کاربر مناسبی پیدا نشد.\n\n"
                "چند لحظه بعد دوباره امتحان کنید."
            )

        set_session(
            user_id,
            partner["user_id"]
        )

        return (
            "🎉 کاربر پیدا شد!\n\n"
            "پیام خود را ارسال کنید.\n\n"
            + CHAT_MENU
        )

    # --------------------------------------------------------
    # پیام داخل چت
    # --------------------------------------------------------

    partner = get_partner(user_id)

    if partner:

        if contains_contact_info(text):

            return (
                "🚫 این پیام ارسال نشد.\n\n"
                "ارسال لینک، آیدی، شماره تلفن یا اطلاعات تماس "
                "در چت ناشناس مجاز نیست."
            )

        # این مقدار باید در Adapter مربوط به SplusLib
        # به partner ارسال شود.

        return {
            "action": "forward",
            "to": partner,
            "text": text
        }

    # --------------------------------------------------------
    # پیام ناشناخته
    # --------------------------------------------------------

    return (
        "دستور شناخته نشد.\n\n"
        "از منوی زیر استفاده کنید:\n\n"
        + MAIN_MENU
    )


# ============================================================
# اتصال به SplusLib
# ============================================================

async def main():

    if TOKEN == "توکن_بات_را_اینجا_بگذار":

        print(
            "❌ ابتدا TOKEN را در ابتدای main.py وارد کنید."
        )

        return

    print("================================")
    print(" FBI CHAT SPLUS")
    print(" SAFE ANONYMOUS CHAT")
    print("================================")

    print(
        "هسته برنامه آماده است."
    )

    print(
        "اتصال event های SplusLib باید مطابق نسخه "
        "نصب‌شده SplusLib انجام شود."
    )


if __name__ == "__main__":

    asyncio.run(main())
