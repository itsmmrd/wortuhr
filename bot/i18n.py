from __future__ import annotations

from bot.constants import LANGUAGES, TOPICS

UI_ASK = (
    "<b>Wortuhr</b>\n\n"
    "Choose the bot language.\n"
    "زبان ربات را انتخاب کنید."
)

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

_EN = {
    "back": "Back",
    "cancel": "Cancel",
    "home": "Home",
    "new_plan": "New plan",
    "my_plans": "My plans",
    "progress": "Progress",
    "review": "Review",
    "settings": "Settings",
    "help": "Help",
    "every_day": "Every day",
    "weekdays": "Weekdays",
    "weekend_days": "Weekend",
    "done": "Done",
    "set_time": "Set a time",
    "pick_random": "Pick a random time",
    "other_language": "Other language",
    "other_topic": "Other topic",
    "other_timezone": "Other timezone",
    "words": "Words",
    "idioms": "Idioms",
    "word": "word",
    "idiom": "idiom",
    "word_title": "Word",
    "idiom_title": "Idiom",
    "pause": "Pause",
    "resume": "Resume",
    "delete": "Delete",
    "send_one": "Send one now",
    "edit_level": "Edit level",
    "edit_topic": "Edit topic",
    "edit_schedule": "Edit schedule",
    "delete_plan": "Delete plan",
    "keep_it": "Keep it",
    "previous": "Previous",
    "next": "Next",
    "learned_words": "Learned words",
    "learned_idioms": "Learned idioms",
    "needs_repeat": "Needs repeat",
    "summary": "Summary",
    "i_learned": "I learned this",
    "repeat_again": "Repeat again",
    "learned_check": "Learned ✓",
    "repeat_check": "Repeat ✓",
    "bot_language": "Bot language",
    "translation_language": "Translation language",
    "timezone": "Timezone",
    "ui_en": "English",
    "ui_fa": "فارسی",
    "wday.0": "Mon",
    "wday.1": "Tue",
    "wday.2": "Wed",
    "wday.3": "Thu",
    "wday.4": "Fri",
    "wday.5": "Sat",
    "wday.6": "Sun",
    "random_short": "random",
    "lessons_one": "1 lesson a day",
    "lessons_many": "{n} lessons a day",
    "times_daily": "{n}× daily",
    "when_today": "today at {time}",
    "when_tomorrow": "tomorrow at {time}",
    "active": "active",
    "paused": "paused",
    "status_label": "Status",
    "when_date": "{day} {month} at {time}",
    "paused_suffix": " · paused",
    "next_random": "Next random send: {when}",
    "level_mid": "Level {level} · {topic}",
    "in_sentence": "In a sentence",
    "where_use": "Where you can use it",
    "plan_footer": "Plan: {language} · {level} · {topic} · {schedule}",
    "hello_name": "Hello {name}.",
    "hello": "Hello.",
    "home_body": "I send words or idioms on the clock you set, with practical examples and translations.",
    "home_extra": "You can run several plans: German A2 work words at 08:00, English idioms at a random afternoon time, and more.",
    "home_stats": "Learned <b>{learned}</b> · to repeat <b>{repeat}</b>",
    "owner_notice": "You are the owner of this bot. Other Telegram accounts cannot use it.\n\n",
    "onboard_intro": (
        "<b>Wortuhr</b>\n\n"
        "I send words and idioms on a schedule you choose, with practical examples and translations.\n\n"
        "First, pick the timezone for those sending times."
    ),
    "settings_body": (
        "<b>Settings</b>\n\n"
        "Timezone: <code>{tz}</code>\n"
        "Card translations: {tr}\n"
        "Bot language: {ui}\n\n"
        "Cards use this timezone and this translation language."
    ),
    "plans_empty": "<b>My plans</b>\n\nYou have no plans yet. A plan is one schedule: language, level, topic, and time.",
    "plans_open": "<b>My plans</b>\n\nOpen a plan to edit it, pause it, or delete it.",
    "delete_ask": "\n\nDelete this plan? Cards you already received stay in your progress.",
    "which_learn": "Which language do you want to learn?",
    "which_level": "Which level, from A1 to C2?",
    "new_level": "Choose a new level.",
    "words_or_idioms": "Words or idioms?",
    "which_topic": "Choose a topic, or type your own. A job or a technical field is fine.",
    "new_topic": "Choose a new topic, or type your own.",
    "pick_day": "Pick at least one day.\n",
    "days_one": "1 day selected.\n",
    "days_many": "{n} days selected.\n",
    "which_days": "Which days of the week? Tap the days, then Done.",
    "how_many": "How many times a day?",
    "lesson_choice": "Lesson {i} of {n}. Set a time, or I will pick a random time.",
    "send_clock": "Send the time for lesson {i}, for example 08:30.",
    "tz_prompt": "Choose the timezone for sending times.",
    "tr_prompt": "Which language should the translations use?",
    "type_language": "Type the language you want to learn. For example: Swedish.",
    "type_topic": "Type a topic, for example nursing, electrical engineering, or job interviews.",
    "tz_custom": "Send a timezone, for example Europe/Berlin or Tehran.",
    "tr_custom": "Send the language for translations, for example Persian.",
    "new_plan_title": "<b>New plan</b>",
    "level_line": "Level {level}",
    "once_a_day": "1 time a day",
    "times_a_day": "{n} times a day",
    "progress_title": "<b>Progress</b>",
    "learned_line": "Learned <b>{n}</b>",
    "repeat_line": "To repeat <b>{n}</b>",
    "sent_line": "Sent <b>{n}</b>",
    "words_bar": "Words {bar} {learned}/{sent}",
    "idioms_bar": "Idioms {bar} {learned}/{sent}",
    "last_7": "<b>Last 7 days</b>",
    "overall": "Overall {bar} {learned}/{sent}",
    "first_card": "Your first card will start the bars.",
    "list_range": "{start}–{end} of {total}\nTap one to open the card.",
    "empty_words": "Words you mark with <b>I learned this</b> will collect here.",
    "empty_idioms": "Idioms you mark with <b>I learned this</b> will collect here.",
    "empty_repeat": "When a card arrives, tap <b>Repeat again</b> and it will collect here.",
    "private_alert": "This bot is private.",
    "private_text": "This Wortuhr bot is private.",
    "wrong": "Something went wrong. Send /start to open the menu.",
    "writing": "Writing your card…",
    "refused": "Telegram refused the message, so I paused your plans.",
    "no_card": "I could not send a card just now.",
    "plan_gone": "That plan is gone.",
    "card_gone": "That card is no longer saved.",
    "not_in_list": "That card is not in your saved list.",
    "marked_learned": "Marked as learned",
    "marked_repeat": "Saved to repeat",
    "summary_need": "Mark a few cards with I learned this, then ask for a summary.",
    "summary_wait": "Writing your summary…",
    "summary_fail": "I could not write a summary just now.",
    "summary_title": "<b>What you have learned</b>\n\n{text}",
    "use_menu": "Use the menu, or send /start.",
    "time_bad": "Use a time like 08:30.",
    "time_taken": "That time is already used. Send a different one.",
    "name_short": "Send a language name, up to 40 characters.",
    "topic_short": "Send a topic, up to 80 characters.",
    "tz_unknown": "I don't know that timezone. Try Europe/Berlin or Asia/Tehran.",
    "err_key": "Groq rejected the API key. Update it with sudo ./install.sh and restart the bot.",
    "err_rate": "Groq is rate-limiting requests. I will try again shortly.",
    "err_write": "Groq could not write this card. I will try again shortly.",
    "err_unreadable": "Groq returned an unreadable card. I will try again shortly.",
    "err_fresh": "I could not prepare a fresh card just now. I will try again shortly.",
    "fail_final": "I could not prepare today's {language} {kind}. The next one will follow your plan.",
    "fail_retry": "I could not prepare your {language} {kind} just now. I will try again shortly.",
    "cmd_start": "Open Wortuhr",
    "cmd_new": "Create a plan",
    "cmd_plans": "Your plans",
    "cmd_progress": "Learning progress",
    "cmd_review": "Cards to repeat",
    "cmd_settings": "Timezone, translation, and language",
    "cmd_help": "How this bot works",
    "cmd_cancel": "Leave the current step",
    "help_body": (
        "<b>Wortuhr</b>\n\n"
        "A plan is a schedule. You can keep several at once.\n"
        "Each plan has a language, a level from A1 to C2, words or idioms, and a topic.\n"
        "A topic can be everyday life, a job, a technical field, or anything you type.\n\n"
        "<b>When cards arrive</b>\n"
        "Choose the days, how many times a day, then a clock time or a random time for each one.\n"
        "A word card has the word, its translation, and 3 short practical sentences.\n"
        "An idiom card has the idiom, its meaning, and 3 situations where you can use it.\n\n"
        "<b>After a card</b>\n"
        "Tap <b>I learned this</b> or <b>Repeat again</b>.\n"
        "Progress keeps the list, a bar, the last 7 days, and a short summary.\n\n"
        "<b>Commands</b>\n"
        "/new — create a plan\n"
        "/plans — edit, pause, or delete a plan\n"
        "/progress — bars, lists, and a summary\n"
        "/review — cards you marked to repeat\n"
        "/settings — bot language, timezone, and translation language\n"
        "/cancel — leave the current step"
    ),
}

_FA = {
    "back": "بازگشت",
    "cancel": "لغو",
    "home": "خانه",
    "new_plan": "برنامه جدید",
    "my_plans": "برنامه‌های من",
    "progress": "پیشرفت",
    "review": "مرور",
    "settings": "تنظیمات",
    "help": "راهنما",
    "every_day": "هر روز",
    "weekdays": "دوشنبه تا جمعه",
    "weekend_days": "شنبه و یکشنبه",
    "done": "تمام",
    "set_time": "ساعت را خودم می‌دهم",
    "pick_random": "ساعت تصادفی بده",
    "other_language": "زبان دیگر",
    "other_topic": "موضوع دیگر",
    "other_timezone": "منطقه زمانی دیگر",
    "words": "واژه‌ها",
    "idioms": "اصطلاح‌ها",
    "word": "واژه",
    "idiom": "اصطلاح",
    "word_title": "واژه",
    "idiom_title": "اصطلاح",
    "pause": "توقف",
    "resume": "ادامه",
    "delete": "حذف",
    "send_one": "یکی الان بفرست",
    "edit_level": "ویرایش سطح",
    "edit_topic": "ویرایش موضوع",
    "edit_schedule": "ویرایش زمان",
    "delete_plan": "حذف برنامه",
    "keep_it": "نگه دار",
    "previous": "قبلی",
    "next": "بعدی",
    "learned_words": "واژه‌های یادگرفته",
    "learned_idioms": "اصطلاح‌های یادگرفته",
    "needs_repeat": "نیاز به تکرار",
    "summary": "خلاصه",
    "i_learned": "این را یاد گرفتم",
    "repeat_again": "دوباره تکرار شود",
    "learned_check": "یاد گرفتم ✓",
    "repeat_check": "تکرار ✓",
    "bot_language": "زبان ربات",
    "translation_language": "زبان ترجمه",
    "timezone": "منطقه زمانی",
    "ui_en": "English",
    "ui_fa": "فارسی",
    "wday.0": "دوشنبه",
    "wday.1": "سه‌شنبه",
    "wday.2": "چهارشنبه",
    "wday.3": "پنجشنبه",
    "wday.4": "جمعه",
    "wday.5": "شنبه",
    "wday.6": "یکشنبه",
    "random_short": "تصادفی",
    "lessons_one": "روزی ۱ درس",
    "lessons_many": "روزی {n} درس",
    "times_daily": "روزی {n}",
    "when_today": "امروز ساعت {time}",
    "when_tomorrow": "فردا ساعت {time}",
    "active": "فعال",
    "paused": "متوقف",
    "status_label": "وضعیت",
    "when_date": "{day} {month} ساعت {time}",
    "paused_suffix": " · متوقف",
    "next_random": "ارسال تصادفی بعدی: {when}",
    "level_mid": "سطح {level} · {topic}",
    "in_sentence": "در جمله",
    "where_use": "کجا می‌توانید استفاده کنید",
    "plan_footer": "برنامه: {language} · {level} · {topic} · {schedule}",
    "hello_name": "سلام {name}.",
    "hello": "سلام.",
    "home_body": "کلمه یا اصطلاح را در ساعتی که تنظیم کرده‌اید می‌فرستم، با مثال کاربردی و ترجمه.",
    "home_extra": "می‌توانید چند برنامه داشته باشید؛ مثلاً واژه‌های آلمانی سطح A2 برای کار، و اصطلاح‌های انگلیسی در یک ساعت تصادفی.",
    "home_stats": "یادگرفته <b>{learned}</b> · برای تکرار <b>{repeat}</b>",
    "owner_notice": "شما صاحب این ربات هستید. حساب‌های دیگر تلگرام نمی‌توانند از آن استفاده کنند.\n\n",
    "onboard_intro": (
        "<b>Wortuhr</b>\n\n"
        "کلمه‌ها و اصطلاح‌ها را طبق برنامه‌ای که می‌چینید می‌فرستم، با مثال کاربردی و ترجمه.\n\n"
        "اول منطقه زمانی ساعت ارسال را انتخاب کنید."
    ),
    "settings_body": (
        "<b>تنظیمات</b>\n\n"
        "منطقه زمانی: <code>{tz}</code>\n"
        "ترجمه کارت‌ها: {tr}\n"
        "زبان ربات: {ui}\n\n"
        "کارت‌ها با این منطقه زمانی و این زبان ترجمه ساخته می‌شوند."
    ),
    "plans_empty": "<b>برنامه‌های من</b>\n\nهنوز برنامه‌ای ندارید. هر برنامه یک زمان‌بندی است: زبان، سطح، موضوع و ساعت.",
    "plans_open": "<b>برنامه‌های من</b>\n\nیک برنامه را باز کنید تا ویرایش، توقف یا حذف شود.",
    "delete_ask": "\n\nاین برنامه حذف شود؟ کارت‌هایی که گرفته‌اید در پیشرفت می‌مانند.",
    "which_learn": "کدام زبان را می‌خواهید یاد بگیرید؟",
    "which_level": "سطح را از A1 تا C2 انتخاب کنید.",
    "new_level": "سطح جدید را انتخاب کنید.",
    "words_or_idioms": "واژه یا اصطلاح؟",
    "which_topic": "موضوع را انتخاب کنید یا خودتان بنویسید. شغل یا زمینه فنی هم مناسب است.",
    "new_topic": "موضوع جدید را انتخاب کنید یا خودتان بنویسید.",
    "pick_day": "حداقل یک روز را انتخاب کنید.\n",
    "days_one": "۱ روز انتخاب شده.\n",
    "days_many": "{n} روز انتخاب شده.\n",
    "which_days": "کدام روزهای هفته؟ روزها را بزنید، بعد تمام.",
    "how_many": "در روز چند بار؟",
    "lesson_choice": "درس {i} از {n}. ساعت را خودتان بدهید، یا من یک ساعت تصادفی انتخاب می‌کنم.",
    "send_clock": "ساعت درس {i} را بفرستید، مثلاً 08:30.",
    "tz_prompt": "منطقه زمانی ساعت ارسال را انتخاب کنید.",
    "tr_prompt": "ترجمه‌ها به کدام زبان باشند؟",
    "type_language": "نام زبانی را که می‌خواهید یاد بگیرید بنویسید. مثلاً: سوئدی.",
    "type_topic": "یک موضوع بنویسید، مثلاً پرستاری، مهندسی برق، یا مصاحبه شغلی.",
    "tz_custom": "یک منطقه زمانی بفرستید، مثلاً Europe/Berlin یا Tehran.",
    "tr_custom": "زبان ترجمه را بنویسید، مثلاً فارسی.",
    "new_plan_title": "<b>برنامه جدید</b>",
    "level_line": "سطح {level}",
    "once_a_day": "روزی ۱ بار",
    "times_a_day": "روزی {n} بار",
    "progress_title": "<b>پیشرفت</b>",
    "learned_line": "یادگرفته <b>{n}</b>",
    "repeat_line": "برای تکرار <b>{n}</b>",
    "sent_line": "فرستاده‌شده <b>{n}</b>",
    "words_bar": "واژه‌ها {bar} {learned}/{sent}",
    "idioms_bar": "اصطلاح‌ها {bar} {learned}/{sent}",
    "last_7": "<b>۷ روز اخیر</b>",
    "overall": "در مجموع {bar} {learned}/{sent}",
    "first_card": "اولین کارت، نوارها را شروع می‌کند.",
    "list_range": "{start}–{end} از {total}\nیکی را بزنید تا کارت باز شود.",
    "empty_words": "واژه‌هایی که با <b>این را یاد گرفتم</b> علامت می‌زنید اینجا جمع می‌شوند.",
    "empty_idioms": "اصطلاح‌هایی که با <b>این را یاد گرفتم</b> علامت می‌زنید اینجا جمع می‌شوند.",
    "empty_repeat": "وقتی کارت می‌آید، <b>دوباره تکرار شود</b> را بزنید تا اینجا جمع شود.",
    "private_alert": "این ربات خصوصی است.",
    "private_text": "این ربات وورتور خصوصی است.",
    "wrong": "مشکلی پیش آمد. /start را بفرستید تا منو باز شود.",
    "writing": "دارم کارت را می‌نویسم…",
    "refused": "تلگرام پیام را نپذیرفت، برای همین برنامه‌ها را متوقف کردم.",
    "no_card": "الان نتوانستم کارت بفرستم.",
    "plan_gone": "این برنامه دیگر وجود ندارد.",
    "card_gone": "این کارت دیگر ذخیره نیست.",
    "not_in_list": "این کارت در فهرست ذخیره شما نیست.",
    "marked_learned": "به‌عنوان یادگرفته علامت شد",
    "marked_repeat": "برای تکرار ذخیره شد",
    "summary_need": "چند کارت را با «این را یاد گرفتم» علامت بزنید، بعد خلاصه بخواهید.",
    "summary_wait": "دارم خلاصه را می‌نویسم…",
    "summary_fail": "الان نتوانستم خلاصه بنویسم.",
    "summary_title": "<b>آنچه یاد گرفته‌اید</b>\n\n{text}",
    "use_menu": "از منو استفاده کنید، یا /start را بفرستید.",
    "time_bad": "ساعت را مثل 08:30 بنویسید.",
    "time_taken": "این ساعت قبلاً انتخاب شده. ساعت دیگری بفرستید.",
    "name_short": "نام زبان را بفرستید، حداکثر ۴۰ حرف.",
    "topic_short": "موضوع را بفرستید، حداکثر ۸۰ حرف.",
    "tz_unknown": "این منطقه زمانی را نمی‌شناسم. Europe/Berlin یا Asia/Tehran را امتحان کنید.",
    "err_key": "گروک کلید API را نپذیرفت. با sudo ./install.sh آن را عوض کنید و ربات را دوباره راه بیندازید.",
    "err_rate": "گروک درخواست‌ها را محدود کرده. کمی بعد دوباره تلاش می‌کنم.",
    "err_write": "گروک نتوانست این کارت را بنویسد. کمی بعد دوباره تلاش می‌کنم.",
    "err_unreadable": "گروک کارت ناخوانا برگرداند. کمی بعد دوباره تلاش می‌کنم.",
    "err_fresh": "الان نتوانستم کارت تازه‌ای آماده کنم. کمی بعد دوباره تلاش می‌کنم.",
    "fail_final": "نتوانستم {kind} {language} امروز را آماده کنم. مورد بعدی طبق برنامه می‌آید.",
    "fail_retry": "الان نتوانستم {kind} {language} را آماده کنم. کمی بعد دوباره تلاش می‌کنم.",
    "cmd_start": "باز کردن وورتور",
    "cmd_new": "برنامه جدید",
    "cmd_plans": "برنامه‌های شما",
    "cmd_progress": "پیشرفت یادگیری",
    "cmd_review": "کارت‌های تکرار",
    "cmd_settings": "زبان، منطقه زمانی و ترجمه",
    "cmd_help": "روش کار ربات",
    "cmd_cancel": "خروج از این مرحله",
    "help_body": (
        "<b>Wortuhr</b>\n\n"
        "هر برنامه یک زمان‌بندی است. چند برنامه می‌توانید همزمان داشته باشید.\n"
        "هر برنامه زبان، سطح از A1 تا C2، واژه یا اصطلاح، و موضوع دارد.\n"
        "موضوع می‌تواند زندگی روزمره، یک شغل، زمینه فنی، یا هر چیزی باشد که خودتان بنویسید.\n\n"
        "<b>کی کارت می‌آید</b>\n"
        "روزها را انتخاب کنید، بعد تعداد بار در روز، و برای هر بار یک ساعت یا زمان تصادفی.\n"
        "کارت واژه، خود واژه، ترجمه‌اش، و ۳ جمله کوتاه کاربردی دارد.\n"
        "کارت اصطلاح، خود اصطلاح، معنی‌اش، و ۳ موقعیتی دارد که می‌توانید از آن استفاده کنید.\n\n"
        "<b>بعد از کارت</b>\n"
        "<b>این را یاد گرفتم</b> یا <b>دوباره تکرار شود</b> را بزنید.\n"
        "پیشرفت، فهرست، نوار، ۷ روز اخیر و یک خلاصه کوتاه را نگه می‌دارد.\n\n"
        "<b>دستورها</b>\n"
        "/new — برنامه جدید\n"
        "/plans — ویرایش، توقف یا حذف برنامه\n"
        "/progress — نوارها، فهرست‌ها و خلاصه\n"
        "/review — کارت‌هایی که برای تکرار علامت زده‌اید\n"
        "/settings — زبان ربات، منطقه زمانی و زبان ترجمه\n"
        "/cancel — خروج از مرحله فعلی"
    ),
}

_LEARN_FA = {
    "de": "آلمانی",
    "en": "انگلیسی",
    "es": "اسپانیایی",
    "fr": "فرانسوی",
    "it": "ایتالیایی",
    "pt": "پرتغالی",
    "nl": "هلندی",
    "pl": "لهستانی",
    "tr": "ترکی",
    "ru": "روسی",
    "fa": "فارسی",
    "ar": "عربی",
    "zh": "چینی",
    "ja": "ژاپنی",
}

_TOPIC_FA = {
    "everyday": "زندگی روزمره",
    "travel": "سفر",
    "food": "غذا و آشپزی",
    "work": "کار و شغل",
    "technical": "فنی",
    "study": "مدرسه و درس",
    "health": "سلامت",
    "home": "خانه و خانواده",
}

_TR_FA = {
    "English": "انگلیسی",
    "German": "آلمانی",
    "Spanish": "اسپانیایی",
    "French": "فرانسوی",
    "Italian": "ایتالیایی",
    "Portuguese": "پرتغالی",
    "Dutch": "هلندی",
    "Polish": "لهستانی",
    "Turkish": "ترکی",
    "Russian": "روسی",
    "Persian": "فارسی",
    "Arabic": "عربی",
    "Chinese": "چینی",
    "Japanese": "ژاپنی",
}

TEXT = {"en": _EN, "fa": {**_EN, **_FA}}


def normalize_ui(code: str | None) -> str:
    return code if code in TEXT else "en"


def t(lang: str | None, key: str, **kwargs: object) -> str:
    chosen = normalize_ui(lang)
    template = TEXT[chosen].get(key) or TEXT["en"].get(key) or key
    rendered = template.format(**kwargs) if kwargs else template
    return localize(chosen, rendered)


def localize(lang: str | None, text: object) -> str:
    rendered = str(text)
    if normalize_ui(lang) == "fa":
        return rendered.translate(_FA_DIGITS)
    return rendered


def language_label(lang: str | None, stored: str) -> str:
    if normalize_ui(lang) != "fa":
        return stored
    for name, code, _flag in LANGUAGES:
        if name.casefold() == stored.casefold():
            return _LEARN_FA.get(code, stored)
    return stored


def topic_label(lang: str | None, stored: str) -> str:
    if normalize_ui(lang) != "fa":
        return stored
    for name, code in TOPICS:
        if name == stored:
            return _TOPIC_FA.get(code, stored)
    return stored


def translation_label(lang: str | None, stored: str) -> str:
    if normalize_ui(lang) != "fa":
        return stored
    return _TR_FA.get(stored, stored)


def ui_label(lang: str | None) -> str:
    return t(lang, "ui_fa" if normalize_ui(lang) == "fa" else "ui_en")
