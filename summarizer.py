import asyncio
from datetime import datetime, timedelta, timezone
import anthropic
from telethon import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv('TG_API_ID'))
API_HASH = os.getenv('TG_API_HASH')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '').strip()
CHANNEL = os.getenv('CHANNEL', '@kikarhashuk')
# In CI we authenticate with a compact StringSession (secret); locally we fall
# back to the on-disk 'session' file. GitHub secrets cap at 64KB, so the old
# base64-of-session-file approach no longer fits — string session is ~350 chars.
STRING_SESSION = os.getenv('TG_STRING_SESSION', '').strip()


def make_session():
    return StringSession(STRING_SESSION) if STRING_SESSION else 'session'


def summarize(messages):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    text = '\n---\n'.join(messages)

    response = client.messages.create(
        model='claude-opus-4-8',
        max_tokens=1500,
        messages=[{
            'role': 'user',
            'content': f"""אתה אנליסט פיננסי חד שמלווה משקיע פרטי. לפניך הודעות גולמיות מערוץ הטלגרם "כיכר השוק" (ערוץ השקעות/כלכלה) מ-7 הימים האחרונים.

המשימה שלך היא לא לסכם ולא לחזור על מה שנכתב — אלא להפיק *תובנות*. ההבדל קריטי:
- סיכום = "דיברו על מניית X ועל ריבית הפד" ❌
- תובנה = "שלוש הודעות נפרדות הזכירו את X בהקשר חיובי — ייתכן מומנטום; שים לב שאין אזכור לסיכון Y שרלוונטי כאן" ✅

תן לי בעברית, חד וקצר:

🎯 *השורה התחתונה* — משפט אחד: מה הדבר הכי חשוב שקרה השבוע בערוץ ולמה אכפת לי.

💡 *תובנות* (2-4 נקודות) — לכל אחת: מה זוהה, מה המשמעות/ההשלכה, ולמה זה לא טריוויאלי. חבר בין הודעות לאורך השבוע, זהה דפוסים, סתירות, או שינוי בסנטימנט. אם מישהו ממליץ על משהו — ציין מי, ומה האינטרס/האמינות אם ידוע.

⚠️ *על מה לשים לב / סיכונים* — דברים שנאמרו בחצי פה, הייפ חשוד, או מידע חסר שהייתי רוצה לבדוק לפני פעולה.

📌 *פעולה אפשרית* — אם בכלל יש משהו ברור לעשות/לבדוק. אם אין — תכתוב "אין פעולה דחופה".

חוקים: אל תמציא. אם הערוץ היה שקט/לא מהותי — תגיד את זה במפורש ואל תנפח. אל תחזור על אותה נקודה פעמיים. עדיף 2 תובנות חדות מ-5 רדודות.

ההודעות:
{text}"""
        }]
    )
    return response.content[0].text


async def main():
    async with TelegramClient(make_session(), API_ID, API_HASH) as client:
        print(f'[{datetime.now()}] Fetching messages...')

        since = datetime.now(timezone.utc) - timedelta(days=7)
        messages = []
        async for message in client.iter_messages(CHANNEL, limit=2000):
            if message.date < since:
                break
            if message.text and message.text.strip():
                messages.append(message.text.strip())

        messages = list(reversed(messages))
        print(f'Found {len(messages)} messages')

        today = datetime.now().strftime('%d/%m/%Y')

        # Single recipient: Kobi only (user reads it there). No copy to Saved Messages.
        KOBI = '+972504501509'

        if not messages:
            await client.send_message(KOBI, f'📭 תובנות שבועיות {today} - לא נמצאו הודעות בשבוע האחרון.')
            return

        summary = summarize(messages)
        msg = f'🧠 תובנות שבועיות - כיכר השוק\n🗓 {today}\n\n{summary}'
        await client.send_message(KOBI, msg)
        print('Summary sent!')


if __name__ == '__main__':
    asyncio.run(main())
