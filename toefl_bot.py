"""
TOEFL iBT (2026 format) practice poster for a Telegram channel. No AI API needed.
4 posts a day (Damascus time), each one dedicated to a single section and
containing ALL task types of that section (like the real exam section):
  07:00 Reading (3 tasks) | 12:00 Listening (4) | 16:00 Writing (3) | 21:00 Speaking (2)
- First post of the day: good-morning + countdown + goal reminder
- Every post: section intro (countdown + goal), then each task with quiz polls,
  spoiler answers and a vocabulary list (English synonym + Arabic translation)
- Last post of the day: farewell
Exercises come from reading*.json, listening*.json, writing*.json, speaking*.json.
Day N uses item N of each task type (the list repeats when it runs out).

Env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL
Optional: START_DATE (default 2026-10-29), TARGET_DATE (default 2026-11-20),
          DRY_RUN=1 (print only, no sending)
"""
import os, io, json, glob, html, time, datetime, requests
from zoneinfo import ZoneInfo

DRY = os.environ.get("DRY_RUN") == "1"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "")
START = datetime.date.fromisoformat(os.environ.get("START_DATE", "2026-10-29"))
TARGET = datetime.date.fromisoformat(os.environ.get("TARGET_DATE", "2026-11-20"))
SLOTS = [(7, "reading"), (12, "listening"), (16, "writing"), (21, "speaking")]
API = f"https://api.telegram.org/bot{TOKEN}"
TLD = {"us": "com", "uk": "co.uk", "au": "com.au"}
GOAL = "🎯 هدفك: التقديم لمنحة إيراسموس موندوس (Erasmus Mundus)"
SECTION_TYPES = {
    "reading": ["complete_words", "daily_life", "academic_passage"],
    "listening": ["listen_response", "listen_conversation", "listen_announcement", "listen_talk"],
    "writing": ["build_sentence", "email", "discussion"],
    "speaking": ["listen_repeat", "interview"],
}
SECTION_NAMES = {"reading": "Reading 📖", "listening": "Listening 🎧",
                 "writing": "Writing ✍️", "speaking": "Speaking 🎤"}
PAUSE = 0 if DRY else 1.3   # seconds between Telegram messages (rate limits)

TYPES = {
    "complete_words": ("Reading 📖", "Complete the Words",
        "عبّي الحروف الناقصة بكل كلمة (10 كلمات). فكّر شو نوع الكلمة (فعل؟ اسم؟) وبعدين كمّل."),
    "daily_life": ("Reading 📖", "Read in Daily Life",
        "اقرا النص بسرعة وجاوب. ركّز على التفاصيل: تواريخ، أرقام، شو المطلوب منك."),
    "academic_passage": ("Reading 📖", "Read an Academic Passage",
        "أول شي دوّر على الفكرة العامة، وبعدين ارجع للتفاصيل. أسئلة الاستنتاج جوابها مو مكتوب حرفياً."),
    "listen_response": ("Listening 🎧", "Listen and Choose a Response",
        "اسمع مرة وحدة بس متل الامتحان، واختار الرد الأنسب للسؤال أو الجملة."),
    "listen_conversation": ("Listening 🎧", "Listen to a Conversation",
        "اسمع مرة وحدة، وركّز على سبب الحوار وشو القرار اللي بيطلع فيه."),
    "listen_announcement": ("Listening 🎧", "Listen to an Announcement",
        "الإعلانات فيها أرقام وتواريخ وتغييرات. اكتبها بمسودة وانت عم تسمع."),
    "listen_talk": ("Listening 🎧", "Listen to an Academic Talk",
        "ركّز على الأمثلة وليش الدكتور عم يذكرها. غالباً في سؤال عن هدف المثال."),
    "build_sentence": ("Writing ✍️", "Build a Sentence",
        "رتّب الكلمات بدفترك وبعدين قارن مع الجواب المخفي. انتبه لترتيب الفاعل والفعل."),
    "email": ("Writing ✍️", "Write an Email",
        "اكتب بدفترك أو لصّق كتابتك بـ Claude ليصحّحها. غطّي كل النقاط المطلوبة بجمل واضحة ومهذّبة."),
    "discussion": ("Writing ✍️", "Writing for an Academic Discussion",
        "خذ موقف واضح وردّ على كلام زميلك بسبب أو مثال. الإضافة الجديدة بتفرق عن مجرد التكرار."),
    "listen_repeat": ("Speaking 🎤", "Listen and Repeat",
        "اسمع كل جملة مرة وحدة وسجّل صوتك وانت عم تعيدها، وبعدين قارن مع النص المخفي."),
    "interview": ("Speaking 🎤", "Take an Interview",
        "جاوب كل سؤال بـ 45 ثانية بدون توقف. سجّل صوتك أو جرّب وضع الصوت بتطبيق Claude ليعطيك ملاحظات."),
}

GREETINGS = [
    "☀️ صباح الخير! اليوم 4 تمارين: قراءة، استماع، كتابة، وتحدّث.\nكل تمرين بيقرّبك من 5.5-6، وكل خطوة بتقرّبك من إيراسموس موندوس 💪",
    "🌅 صباح النور! اليوم مو يوم للتشتت.\nالهدف واضح: منحة إيراسموس موندوس. حلّ التمارين أول بأول وما تأجّل 🎯",
    "☕ صباح الخير! بلّش بنشاط.\nتذكّر ليش عم تتعب: الدراسة بأوروبا بتنتظرك، والتوفل جسرك لهناك 🌍",
    "🌞 يوم موفّق! أول تمرين جاهز.\nالنجاح بيجي من الاستمرار اليومي، مو من الحماس لمرة وحدة ✨",
]
FAREWELLS = [
    "🌙 تصبح على خير! خلصت تمارين اليوم، أحسنت.\nراجع المفردات الجديدة قبل ما تنام، ونتلاقى بكرا بنفس الهمّة 💫",
    "🌟 انتهى يوم التدريب! كل تمرين حليته بيقرّبك من إيراسموس موندوس.\nنوم الهنا 😴",
    "🌃 مساء الخير ونوم العافية.\nلا تنسَ: الاستمرار أهم من الكمال. بكرا بنكمّل 💪",
    "🌙 كفّيت اليوم! ارتاح، وبكرا أقوى.\nالهدف قدّامك والوقت بيمشي بصالحك لو التزمت 🎯",
]


def send(method, files=None, **kw):
    if DRY:
        print(f"[{method}]", {k: (v if len(str(v)) < 80 else str(v)[:80] + '…') for k, v in kw.items()})
        return
    for attempt in range(5):
        r = requests.post(f"{API}/{method}", data=kw, files=files, timeout=90)
        if r.ok:
            time.sleep(PAUSE)
            return
        if r.status_code == 429:
            wait = r.json().get("parameters", {}).get("retry_after", 5)
            time.sleep(wait + 1)
            if files:  # rewind file-like data before retrying
                files = {k: (v[0], v[1], v[2]) for k, v in files.items()}
            continue
        raise SystemExit(f"Telegram error: {r.text}")
    raise SystemExit("Telegram error: too many retries")


def msg(text, html_mode=False):
    assert len(text) <= 4096, f"message too long ({len(text)})"
    kw = {"parse_mode": "HTML"} if html_mode else {}
    send("sendMessage", chat_id=CHANNEL, text=text, **kw)


def spoiler(label, body):
    msg(f"{label}\n<tg-spoiler>{html.escape(body)}</tg-spoiler>", html_mode=True)


def make_audio(segments):
    from gtts import gTTS
    buf = io.BytesIO()
    for accent, text in segments:
        gTTS(text, lang="en", tld=TLD.get(accent, "com")).write_to_fp(buf)
    return buf.getvalue()


def send_audio(data, title):
    send("sendAudio", files={"audio": ("audio.mp3", data, "audio/mpeg")},
         chat_id=CHANNEL, title=title)


def load_pool(section):
    pool = []
    for path in sorted(glob.glob(f"{section}*.json")):
        with open(path, encoding="utf-8") as f:
            pool += json.load(f)
    return pool


def countdown(today):
    d = (TARGET - today).days
    label = TARGET.strftime("%d/%m")
    if d > 1:
        return f"⏳ باقي {d} يوم على {label}"
    if d == 1:
        return f"⏳ باقي يوم واحد على {label}"
    if d == 0:
        return f"⏳ اليوم هو {label}!"
    return f"⏳ عدّى موعد {label}، كمّل بنفس الجدّية"


def post_item(item, today, day_no, i=1, n=1):
    section, task, tip = TYPES[item["type"]]
    t = item["type"]
    msg(f"📌 <b>مهمة {i}/{n}</b> · {section}\n{task} · {html.escape(item['topic'])}\n\n💡 {tip}",
        html_mode=True)

    segs = item.get("audio")
    if segs:
        if t == "listen_repeat":
            for i, (accent, text) in enumerate(segs, 1):
                send_audio(b"" if DRY else make_audio([(accent, text)]), f"Repeat {i}")
        else:
            send_audio(b"" if DRY else make_audio(segs), f"{task} – {item['topic']}")
            msg("🎧 اسمع مرة وحدة بس متل الامتحان، وبعدين جاوب.")
    elif "text" in item:
        msg(item["text"])

    for q in item.get("questions", []):
        assert len(q["q"]) <= 300 and len(q["explanation"]) <= 200
        assert all(len(o) <= 100 for o in q["options"])
        send("sendPoll", chat_id=CHANNEL, question=q["q"], type="quiz",
             options=json.dumps(q["options"], ensure_ascii=False),
             correct_option_id=q["correct"], is_anonymous="true",
             explanation=q["explanation"])

    if "answer" in item:
        spoiler("✅ الجواب / النموذج (اضغط لتكشف بعد ما تحاول):", item["answer"])
    if segs:
        spoiler("📝 النص المسموع للمراجعة:", "\n".join(s[1] for s in segs))

    lines = [f"• {w} — {syn} — {ar}" for w, syn, ar in item["vocab"]]
    msg("📖 مفردات التمرين (كلمة — مرادف بالإنكليزي — ترجمة):\n" + "\n".join(lines))


def tasks_for(section, day):
    """One item per task type of the section (day N -> item N of each type)."""
    pool = load_pool(section)
    by_type = {t: [x for x in pool if x["type"] == t] for t in SECTION_TYPES[section]}
    return [items[day % len(items)] for items in by_type.values() if items]


def main():
    now = datetime.datetime.now(ZoneInfo("Asia/Damascus"))
    today = now.date()
    day = max((today - START).days, 0)
    slot = max([i for i, (h, _) in enumerate(SLOTS) if now.hour >= h] or [0])
    section = SLOTS[slot][1]
    tasks = tasks_for(section, day)

    if slot == 0:
        msg(GREETINGS[day % len(GREETINGS)] + "\n\n" + countdown(today) + "\n" + GOAL)
    msg(f"📚 <b>TOEFL – {SECTION_NAMES[section]}</b> · يوم {day + 1}\n"
        f"{len(tasks)} مهام اليوم، حلّها بالترتيب متل الامتحان.\n"
        f"{countdown(today)} · {GOAL}", html_mode=True)
    for i, item in enumerate(tasks, 1):
        post_item(item, today, day + 1, i, len(tasks))
    if slot == len(SLOTS) - 1:
        msg(FAREWELLS[day % len(FAREWELLS)])


if __name__ == "__main__":
    main()
