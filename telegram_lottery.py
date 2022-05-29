import os
import sqlite3
from dblite import aioDbLite
from pyrogram import Client
from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import (Message)
from pyrogram.methods.utilities.idle import idle
from pyrogram.enums import (ChatMemberStatus, ChatMembersFilter)
from pyrogram.types import BotCommand
from pyrogram.errors.exceptions.bad_request_400 import MessageNotModified
from dotenv import load_dotenv
from typing import TypedDict

load_dotenv()
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

main_text_lottery = """Розыгрыш **"[title]"** начался!

Чтобы принять участие нужно нажать на `🎲` и отправить его в чат.
Если это не получается, можно найти нужный эмодзи написав в пустом сообщении `dice` или `кубик`, в появившейся подсказке выбрать эмодзи кубика и отправить сообщение содержащее только этот эмодзи в чат.

Розыгрыш будет продолжаться несколько раундов среди участников с самыми высокими результатами, пока не останется один победитель.

В каждом раунде считается только первый отправленный кубик.

Статус: **[status]**
Раунд: **[round]**
Участники раунда: 
[participants]
"""

text_winner = """
Розыгрыш **"[title]"** окочен!
🥳🥳🥳🥳🥳🥳🥳🥳🥳

Поздравляем **[[user_name]](tg://user?id=[user_id])** с победой!!!
🎉🎉🎉🎊🎊🎊👏👏👏
"""

class LotteryType(TypedDict):
    id: int
    chat_id: int
    message_id: int
    title: str
    status: int
    # dateCreated: datetime.datetime
    round: int

class ParticipantType(TypedDict):
    user_id: int
    user_name: int
    lottery_id: int
    tiket: int
    lottery_round: str
    
def get_main_message(lottery_title: str, lottery_round: int, lottery_status: str, lottery_participants: str):
    return main_text_lottery \
        .replace('[title]', lottery_title) \
        .replace('[round]', str(lottery_round)) \
        .replace('[status]', lottery_status) \
        .replace('[participants]', lottery_participants)
    
def get_winner_message(lottery_title: str, lottery_round: int, user_id: int, user_name: str):
    return text_winner \
        .replace('[title]', lottery_title) \
        .replace('[round]',  str(lottery_round)) \
        .replace('[user_id]', str(user_id)) \
        .replace('[user_name]', user_name)

def render_lottery_status(lottery_status: int, lottery_round: int):
    status = "розыгрыш завершен"
    if lottery_status:
        if lottery_round > 1:
            status = "отсев участников"
        else:
            status = "принимаются участники"
    return status

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
            # dateCreated='timestamp',
            round='int'
        )
        await self.aiodb.create(
            'participants', 
            id='INTEGER PRIMARY KEY AUTOINCREMENT',
            user_id='int',
            user_name='TEXT NOT NULL',
            lottery_id='int',
            tiket='int',
            lottery_round='int',
        )
        await self.aiodb.cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS "only_one_user_per_round" ON participants("user_id", "lottery_id", "lottery_round");')
        await self.app.start()
        await self.app.set_bot_commands([
            BotCommand("startlottery", "Начать новый розыгрыш"),
            BotCommand("stoplottery", "Остановить розыгрыш"),
            BotCommand("nextround", "Следующий раунд розыгрыша")
        ])
        await idle()
        await self.app.stop()
        await self.aiodb.close()

    async def load_active_lottery(self, chat_id: int) -> LotteryType:
        lotteries_raw = await self.aiodb.select('lotteries', '*', chat_id=chat_id, status=1)
        lottery: LotteryType = {}
        if len(lotteries_raw) > 0:
            lottery = {
                "id": lotteries_raw[0][0],
                "chat_id": lotteries_raw[0][1],
                "message_id": lotteries_raw[0][2],
                "title": lotteries_raw[0][3],
                "status": lotteries_raw[0][4],
                # "dateCreated": lotteries_raw[0][5],
                "round": lotteries_raw[0][5],
            }
        return lottery

    async def load_participants(self, lottery_id: int, lottery_round: int, **kwargs) -> list[ParticipantType]:
        participants_raw = await self.aiodb.select('participants', '*', lottery_id=lottery_id, lottery_round=lottery_round, **kwargs)
        participants: list[ParticipantType] = []
        for participant_raw in participants_raw:
            participants.append({
                "id": participant_raw[0],
                "user_id": participant_raw[1],
                "user_name": participant_raw[2],
                "lottery_id": participant_raw[3],
                "tiket": participant_raw[4],
                "lottery_round": participant_raw[5],
            })
        return participants

    async def get_round_winners(self, lottery_id: int, lottery_round: int) -> list[ParticipantType]:
        participants_all = await self.load_participants(lottery_id, lottery_round)
        participants: dict[int, list[ParticipantType]] = {}
        for participant in participants_all:
            if not participant["tiket"] in participants:
                participants[participant["tiket"]] = []
            participants[participant["tiket"]].append(participant)
        winners_ticket = max(participants.keys())
        return participants[winners_ticket]

    async def set_winners_active(self, participants: list[ParticipantType], new_round: int):
        for participant in participants:
            await self.aiodb.add(
                'participants', 
                user_id=participant['user_id'],
                user_name=participant['user_name'],
                lottery_id=participant['lottery_id'],
                tiket=0,
                lottery_round=new_round,
            )


    def render_participants(self, lottery_participants: list[ParticipantType]) -> str:
        sorted_participants = sorted(lottery_participants, key=lambda d: d['tiket']) 
        participants = "    "
        if len(sorted_participants) == 0:
            participants += "__пока нет участников__"
        else:
            i = 0
            for participant in sorted_participants:
                tiket = participant['tiket']
                if tiket == 0:
                    tiket = "ожидание броска"
                participants += f"[{participant['user_name']}](tg://user?id={participant['user_id']}) - **{tiket}**"
                if participants != "":
                    participants += "\n    "
                i += 1
                if i > 20:
                    participants += f"\n    ...\n    и еще {len(sorted_participants)-i} с меньшими результатами..."
        return participants

    # start lottery
    async def startlottery_handler(self, client: Client, message: Message):
        lottery_title = message.command
        lottery_title.pop(0)
        lottery_title = ' '.join(lottery_title)
        lottery_round = 1
        lottery_status = 1
        lottery_participants = ""
        user_chat_data = await client.get_chat_member(
            chat_id=message.chat.id,
            user_id=message.from_user.id
        )
        if user_chat_data.status == ChatMemberStatus.ADMINISTRATOR or user_chat_data.status == ChatMemberStatus.OWNER:
            already_exists = await self.load_active_lottery(message.chat.id)
            if not already_exists:
                if len(lottery_title) == 0:
                    await message.reply('Повторите команду дописав через пробел заголовок розыгрыша!')
                else:
                    reply_message = await client.send_message(
                        chat_id=message.chat.id,
                        text=get_main_message(
                            lottery_title,
                            lottery_round,
                            render_lottery_status(lottery_status, lottery_round),
                            lottery_participants,
                        ),
                        disable_web_page_preview=True
                    )
                    await self.aiodb.add(
                        'lotteries', 
                        chat_id=message.chat.id,
                        message_id=reply_message.id,
                        title=lottery_title,
                        status=lottery_status,
                        # dateCreated=datetime.datetime.now(),
                        round=lottery_round
                    )
                    try:
                        await client.pin_chat_message(
                            chat_id=message.chat.id,
                            message_id=reply_message.id
                        )
                    except:
                        pass
            else:
                await client.send_message(
                    chat_id=message.chat.id,
                    text='Нельзя начать новый розыгрыш пока идёт другой активный розыгрыш.',
                    reply_to_message_id=already_exists['message_id']
                )
        else:
            await message.reply('Только админы могут начать новую лотерею.')

    async def _stoplottery(self, client: Client, message: Message, notify_message=True):
        active_lottery = await self.load_active_lottery(message.chat.id)
        if active_lottery:
            new_status = 0
            await self.aiodb.update('lotteries', status=new_status, id=active_lottery['id'])
            if notify_message:
                await client.send_message(
                    chat_id=message.chat.id,
                    text='Розыгрыш закончен.',
                    reply_to_message_id=active_lottery['message_id'],
                )
            # Update message
            lottery_participants = await self.load_participants(active_lottery['id'], active_lottery['round'])
            text_participants = self.render_participants(lottery_participants)
            try:
                await client.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=active_lottery['message_id'],
                    text=get_main_message(
                        active_lottery['title'],
                        active_lottery['round'],
                        render_lottery_status(new_status, active_lottery['round']),
                        text_participants,
                    ),
                    disable_web_page_preview=True,
                )
            except MessageNotModified:
                pass
            try:
                await client.unpin_chat_message(
                    chat_id=message.chat.id,
                    message_id=active_lottery['message_id']
                )
            except:
                pass
        else:
            await message.reply('Нет активных розыгрышей!')
    
    # stop lottery
    async def stoplottery_handler(self, client: Client, message: Message):
        user_chat_data = await client.get_chat_member(
            chat_id=message.chat.id,
            user_id=message.from_user.id
        )
        if user_chat_data.status == ChatMemberStatus.ADMINISTRATOR or user_chat_data.status == ChatMemberStatus.OWNER:
            await self._stoplottery(client, message)
        else:
            await message.reply('Только админы могут остановить розыгрыш.')
    
    # next round
    async def _nextround(self, client: Client, message: Message):
        active_lottery = await self.load_active_lottery(message.chat.id)
        if active_lottery:
            round_winners = await self.get_round_winners(active_lottery['id'], active_lottery['round'])
            if len(round_winners) == 1:
                await client.send_message(
                    chat_id=message.chat.id,
                    text=get_winner_message(
                        active_lottery['title'],
                        active_lottery['round'],
                        round_winners[0]['user_id'],
                        round_winners[0]['user_name'],
                    )
                )
                await self._stoplottery(client, message, False)
            else:
                new_round = active_lottery['round'] + 1
                await self.set_winners_active(round_winners, new_round)
                await message.reply('Начинается следующий раунд!')
                # Update message
                lottery_participants = await self.load_participants(active_lottery['id'], new_round)
                text_participants = self.render_participants(lottery_participants)
                try:
                    await client.unpin_chat_message(
                        chat_id=message.chat.id,
                        message_id=active_lottery['message_id']
                    )
                except:
                    pass
                next_message = await client.send_message(
                    chat_id=message.chat.id,
                    text=get_main_message(
                        active_lottery['title'],
                        new_round,
                        render_lottery_status(active_lottery['status'], active_lottery['round']),
                        text_participants,
                    ),
                    disable_web_page_preview=True,
                )
                await self.aiodb.update('lotteries', message_id=next_message.id, round=new_round, id=active_lottery['id'])
                try:
                    await client.pin_chat_message(
                        chat_id=message.chat.id,
                        message_id=next_message.id
                    )
                except:
                    pass
        else:
            await message.reply('Нет активных розыгрышей!')

    async def nextround_handler(self, client: Client, message: Message):
        user_chat_data = await client.get_chat_member(
            chat_id=message.chat.id,
            user_id=message.from_user.id
        )
        if user_chat_data.status == ChatMemberStatus.ADMINISTRATOR or user_chat_data.status == ChatMemberStatus.OWNER:
            await self._nextround(client, message)
        else:
            await message.reply('Только админы могут начать следующий раунд.')

    async def dice_handler(self, client: Client, message: Message):
        active_lottery = await self.load_active_lottery(message.chat.id)
        if active_lottery:
            # засчитываем только первый бросок
            participants = await self.load_participants(active_lottery['id'], active_lottery['round'], user_id=message.from_user.id)
            if len(participants) == 0 or participants[0]['tiket'] == 0:
                username = message.from_user.username
                if message.from_user.first_name:
                    username = message.from_user.first_name
                    if message.from_user.last_name:
                        username += " " + message.from_user.last_name
                new_record = True
                if len(participants) > 0 and participants[0]['tiket'] == 0:
                    await self.aiodb.update(
                        'participants', 
                        user_id=message.from_user.id,
                        user_name=username,
                        lottery_id=active_lottery['id'],
                        tiket=message.dice.value,
                        lottery_round=active_lottery['round'],
                        id=participants[0]['id']
                    )
                else:
                    try:
                        await self.aiodb.add(
                            'participants', 
                            user_id=message.from_user.id,
                            user_name=username,
                            lottery_id=active_lottery['id'],
                            tiket=message.dice.value,
                            lottery_round=active_lottery['round'],
                        )
                    except sqlite3.IntegrityError:
                        new_record = False
                if new_record:
                    await message.reply(f"Результат броска (**{message.dice.value}**) засчитан")
                # Update message
                lottery_participants = await self.load_participants(active_lottery['id'], active_lottery['round'])
                text_participants = self.render_participants(lottery_participants)
                try:
                    await client.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=active_lottery['message_id'],
                        text=get_main_message(
                            active_lottery['title'],
                            active_lottery['round'],
                            render_lottery_status(active_lottery['status'], active_lottery['round']),
                            text_participants,
                        ),
                        disable_web_page_preview=True,
                    )
                except MessageNotModified:
                    pass
                # если раунд > 1 и все участники отправили результаты - начинать следующий раунд
                if active_lottery['round'] > 1:
                    this_round_participants = await self.load_participants(active_lottery['id'], active_lottery['round'])
                    this_round_participants = [d for d in this_round_participants if d['tiket'] > 0]
                    previous_round_winners = await self.get_round_winners(active_lottery['id'], active_lottery['round'] - 1)
                    if len(this_round_participants) == len(previous_round_winners):
                        await self._nextround(client, message)

    def startBot(self):
        self.app = Client(
            "lottery_bot",
            api_id=API_ID, api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )
        self.app.add_handler(MessageHandler(self.startlottery_handler, filters.command(["startlottery"])))
        self.app.add_handler(MessageHandler(self.stoplottery_handler, filters.command(["stoplottery"])))
        self.app.add_handler(MessageHandler(self.nextround_handler, filters.command(["nextround"])))
        self.app.add_handler(MessageHandler(self.dice_handler, filters.dice))
        self.app.run(self.connect())

bot = LotteryBot()
bot.startBot()
