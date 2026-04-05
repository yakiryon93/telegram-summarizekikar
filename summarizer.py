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
        model='claude-opus-4-6',
        max_tokens=1500,
        messages=[{
            'role': 'user',
            'content': f"""להלן הודעות מערוץ טלגרם "כיכר השוק" מ-24 השעות האחרונות:

{text}

סכם בעברית:
1. הנושאים המרכזיים שעלו היום
2. מידע כלכלי/השקעות חשוב
3. כל דבר בולט שכדאי לדעת

היה תמציתי וברור. אל תחזור על אותו מידע פעמיים."""
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
        msg = f'📊 סיכום יומי - כיכר השוק\n🗓 {today}\n\n{summary}'
        await client.send_message('me', msg)
        await client.send_message('+972504501509', msg)
        print('Summary sent!')


if __name__ == '__main__':
    asyncio.run(main())
