#This script is independet of lib or python version (tested on python 2.7 and 3.5)

import telegram
#token that can be generated talking with @BotFather on telegram
from tinydb import TinyDB, Query

from config import MY_TG_TOKEN, MY_HOST_URL

db = TinyDB('db.json')
usertable = db.table('user_profile')

def send(msg, chat_id, token=MY_TG_TOKEN):
    """
    Send a mensage to a telegram user specified on chatId
    chat_id must be a number!
    """
    bot = telegram.Bot(token=token)
    bot.sendMessage(chat_id=chat_id, text=msg)


def job():
    User = Query()
    for user in usertable.all():
        if user['waiting_reply'] and user['hours_last_seen'] < 3:
            continue
        if user['state'] == 'resting':
            if user['hours_last_seen'] > 8:
                if not user['waiting_reply']:
                    prompt = (
                        '你是輔助用戶安排工作的助手，'
                        f'現在請使用指定的語言【{user["language"]}】'
                        '詢問用戶今天打算做些什麼，即使用戶有可能在睡覺。')
                    msg = requests.get(MY_HOST_URL).json({"text": prompt})['result']
                    send(msg, user['id'])
                    usertable.update(
                        {'waiting_reply': True},
                        User.id == user['id'])
            else:
                usertable.update(
                    {'hours_last_seen': user['hours_last_seen'] + 1},
                    User.id == user['id'])
        if user['state'][:8] == 'working:':
            prompt = (f'根據之前的記錄："""{user["state"]}"""\n'
                      '現在請使用指定的語言【中文】詢問用戶是否已經完成了之前的事情。')
            msg = requests.get(MY_HOST_URL).json({"text": prompt})['result']
            send(msg, user['id'])
            usertable.update({'waiting_reply': True}, User.id == user['id'])
        # log to csv (user['id'], user['state'], update.message.text, llm_out)
