import asyncio
from datetime import datetime, timedelta, timezone
import anthropic
from telethon import TelegramClient
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv('TG_API_ID'))
API_HASH = os.getenv('TG_API_HASH')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '').strip()
CHANNEL = os.getenv('CHANNEL', '@kikarhashuk')


def summarize(messages):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    text = '\n---\n'.join(messages)

    response = client.messages.create(
        model='claude-opus-4-8',
        max_tokens=1500,
        messages=[{
            'role': 'user',
            'content': f"""אתה אנליסט פיננסי חד שמלווה משקיע פרטי. לפניך הודעות גולמיות מערוץ הטלגרם "כיכר השוק" (ערוץ השקעות/כלכלה) מ-24 השעות האחרונות.

המשימה שלך היא לא לסכם ולא לחזור על מה שנכתב — אלא להפיק *תובנות*. ההבדל קריטי:
- סיכום = "דיברו על מניית X ועל ריבית הפד" ❌
- תובנה = "שלוש הודעות נפרדות הזכירו את X בהקשר חיובי — ייתכן מומנטום; שים לב שאין אזכור לסיכון Y שרלוונטי כאן" ✅

תן לי בעברית, חד וקצר:

🎯 *השורה התחתונה* — משפט אחד: מה הדבר הכי חשוב שקרה היום בערוץ ולמה אכפת לי.

💡 *תובנות* (2-4 נקודות) — לכל אחת: מה זוהה, מה המשמעות/ההשלכה, ולמה זה לא טריוויאלי. חבר בין הודעות, זהה דפוסים, סתירות, או שינוי בסנטימנט. אם מישהו ממליץ על משהו — ציין מי, ומה האינטרס/האמינות אם ידוע.

⚠️ *על מה לשים לב / סיכונים* — דברים שנאמרו בחצי פה, הייפ חשוד, או מידע חסר שהייתי רוצה לבדוק לפני פעולה.

📌 *פעולה אפשרית* — אם בכלל יש משהו ברור לעשות/לבדוק. אם אין — תכתוב "אין פעולה דחופה".

חוקים: אל תמציא. אם הערוץ היה שקט/לא מהותי — תגיד את זה במפורש ואל תנפח. אל תחזור על אותה נקודה פעמיים. עדיף 2 תובנות חדות מ-5 רדודות.

ההודעות:
{text}"""
        }]
    )
    return response.content[0].text


async def main():
    async with TelegramClient('session', API_ID, API_HASH) as client:
        print(f'[{datetime.now()}] Fetching messages...')

        since = datetime.now(timezone.utc) - timedelta(hours=24)
        messages = []
        async for message in client.iter_messages(CHANNEL, limit=500):
            if message.date < since:
                break
            if message.text and message.text.strip():
                messages.append(message.text.strip())

        messages = list(reversed(messages))
        print(f'Found {len(messages)} messages')

        today = datetime.now().strftime('%d/%m/%Y')

        if not messages:
            await client.send_message('me', f'📭 סיכום יומי {today} - לא נמצאו הודעות ב-24 השעות האחרונות.')
            return

        summary = summarize(messages)
        msg = f'🧠 תובנות יומיות - כיכר השוק\n🗓 {today}\n\n{summary}'
        await client.send_message('me', msg)
        await client.send_message('+972504501509', msg)
        print('Summary sent!')


if __name__ == '__main__':
    asyncio.run(main())
