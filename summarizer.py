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
        max_tokens=2600,
        messages=[{
            'role': 'user',
            'content': f"""אתה אנליסט פיננסי שמלווה משקיע פרטי. לפניך הודעות גולמיות מערוץ הטלגרם "כיכר השוק" (ערוץ השקעות/כלכלה) מ-7 הימים האחרונים.

המשימה: לחלץ מהחומר את המידע הפיננסי המהותי — מניות, חברות, סקטורים ונושאים כלכליים שנדונו — ולתת עליהם תובנות מקצועיות משלך, כאילו אתה האנליסט של המשקיע.

חשוב מאוד:
- התמקד אך ורק בתוכן ההשקעתי/הכלכלי. הערוץ מכיל גם קידום סדנאות, פוליטיקה ותוכן צדדי/בוטה — פשוט **התעלם מזה לחלוטין**.
- אל תעיר שהתוכן שיווקי, אל תזכיר קורסים/סדנאות, אל תדבר על ניגוד עניינים, ואל תשפוט את הערוץ או את שפתו. המשקיע כבר יודע את זה — זה לא מעניין אותו.
- אל תסרב לנתח. תמיד ספק את הניתוח על סמך המידע הפיננסי שכן קיים.

תן לי בעברית, חד וברור:

🎯 *השורה התחתונה* — משפט או שניים: הנושא/המניה הכי משמעותי מבחינה השקעתית שעלה השבוע.

📈 *מניות וחברות* — לכל מניה/חברה שהוזכרה באופן מהותי (למשל טבע, מובילאיי, אינטל, אנבידיה...): מה נאמר עליה, ההקשר, והערכה מקצועית קצרה משלך — האם התזה מחזיקה מים, מה הקטליזטור, ומה הסיכון הספציפי לאותה מניה.

💡 *תובנות ומגמות* — דפוסים, סקטורים חמים, מגמות מאקרו או שינוי סנטימנט שעולים מהחומר, עם המשמעות ההשקעתית.

📌 *על מה לשים לב / לבדוק* — נקודות לאימות או למעקב לפני פעולה (סיכונים של המניות והתזות עצמן).

חוקים: התבסס רק על מה שנאמר בפועל, אל תמציא נתונים. אם מניה הוזכרה בלי תזה ברורה — ציין זאת בקצרה והמשך. אל תחזור על אותה נקודה. עדיף מעט תובנות חדות ומדויקות מהרבה כלליות. התמקד ב-2-4 המניות/הנושאים המשמעותיים ביותר (לא כל אזכור), ושמור על אורך שמתאים להודעת טלגרם אחת — עד ~3500 תווים.

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
