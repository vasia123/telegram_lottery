
import os
from dblite import aioDbLite
from pyrogram import Client
from pyrogram import filters
from pyrogram.types import (Message)
from pyrogram.methods.utilities.idle import idle
from pyrogram.enums import ChatMemberStatus
from dotenv import load_dotenv

load_dotenv()
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

text_new_lottery = """Розыгрыш **"[title]"** начался!

Чтобы принять участие нужно нажать на `🎲` и отправить его в чат.
Если это не получается, можно найти нужный эмодзи написав в пустом сообщении `dice` или `кубик`, в появившейся подсказке выбрать эмодзи кубика и отправить сообщение содержащее только этот эмодзи в чат.

Розыгрыш будет продолжать несколько раундов среди участников с самыми высокими результатами, пока не останется один победитель.

В каждом раунде считается только первый отправленный кубик.

__Генерация значения кубика происходит на серверах телеграмма, этим гарантируется честность результата.__
__Код бота доступен в открытом доступе: __


Текущий раунд: **[round]**
Участники раунда: [participants]
"""

class LotteryBot:
    aiodb: aioDbLite = None
    app: Client = None
        
    async def connect(self):
        """Connect to the database."""
        self.aiodb = await aioDbLite('tgbot.db')
        await self.aiodb.create(
            'lotteries', 
            id='INTEGER PRIMARY KEY AUTOINCREMENT',
            chat_id='int',
            message_id='int',
            title='TEXT NOT NULL',
            status='int(1)',
            dateCreated='timestamp',
            round='int'
        )
        await self.aiodb.create(
            'participants', 
            user_id='int',
            lottery_id='int',
            tiket='int',
            round='int',
        )
        await self.app.start()
        await idle()
        await self.app.stop()
        await self.aiodb.close()

    def startBot(self):

        self.app = Client(
            "lottery_bot",
            api_id=API_ID, api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )
        # start lottery
        @self.app.on_message(filters.command(["startlottery"]))
        async def startlottery(client: Client, message: Message):
            print(message)
            lottery_title = message.command
            lottery_title.pop(0)
            lottery_title = ' '.join(lottery_title)
            if len(lottery_title) == 0:
                await message.reply('Заголовок розыгрыша не должен быть пустым!')
            else:
                user_chat_data = await client.get_chat_member(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id
                )
                print(user_chat_data)
                print(user_chat_data.status)
                if user_chat_data.status == ChatMemberStatus.ADMINISTRATOR or user_chat_data.status == ChatMemberStatus.OWNER:
                    await message.reply(
                        text_new_lottery
                            .replace('[title]', lottery_title)
                            .replace('[round]', 1)
                            .replace('[participants]', "пока нет")
                    )
                    
                    # print(await aiodb.data('users'))
                    # await aiodb.add('users', id=1, name='Jhon', age=32, pos='Developer')
                    # await aiodb.add('users', id=2, name='Doe', age=30, pos='Manager')
                    # await aiodb.add('users', id=3, name='Rio', age=29, pos='Marketing')
                    # print(await aiodb.data('users'))
                    # await aiodb.remove('users', id=3)
                    # print(await aiodb.data('users'))
                    # await aiodb.update('users', age=31, pos='CEO', id=1)
                    # print(await aiodb.data('users'))
                    # print(await aiodb.select('users', '*', id=1))
                else:
                    await message.reply('Только админы могут начать новую лотерею.')

        # stop lottery
        @self.app.on_message(filters.command(["stoplottery"]))
        async def stoplottery(client: Client, message: Message):
            # message.chat.id
            await message.reply('Розыгрыш остановлен.')

        # next round
        @self.app.on_message(filters.command(["nextround"]))
        async def nextround(client: Client, message: Message):
            await message.reply('Начинается следующий раунд.')
            # await message.reply('Только админы могут начать следующий раунд.')

        @self.app.on_message(filters.dice)
        async def dice(client: Client, message: Message):
            print(message)
            await message.reply(message.dice.value)

        self.app.run(self.connect())

bot = LotteryBot()
bot.startBot()
