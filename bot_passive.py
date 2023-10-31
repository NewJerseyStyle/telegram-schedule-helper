import requests
import json

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from tinydb import TinyDB, Query

from config import MY_TG_TOKEN, MY_HOST_URL

db = TinyDB('db.json')
usertable = db.table('user_profile')

async def help_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    User = Query()
    user = usertable.search(User.id == update.effective_user.id)[0]
    # 用戶是要睡覺或者結束今天的工作了嗎？
    prompt = ('整理以下我們對用戶的認識 JSON 變成清單格式，'
            f'並以指定語言【{user["language"]}】展示給用戶：')
    # 3: Query the application and print the result.
    llm_out = requests.post(MY_HOST_URL, json={
        "text": prompt+f'"""{json.dumps(user)}"""'
    }).json()['result']
    await update.message.reply_text(llm_out)


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')
    await update.message.reply_text(f'Do you text in English?\n還是你會希望用中文聊？')
    usertable.insert({
        'id': update.effective_user.id,
        'name': update.effective_user.first_name,
        'state': 'new',
        'language': '',
        'hours_last_seen': 0,
        'waiting_reply': False})


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    User = Query()
    user = usertable.search(User.id == update.effective_user.id)[0]
    usertable.update({'hours_last_seen': 0}, User.id == user['id'])
    # 用戶是要睡覺或者結束今天的工作了嗎？
    llm_out = ''
    if user['state'] not in ['new']:
        prompt = ('根據以下文字判別用戶是要睡覺或者結束今天的工作了嗎？'
                    '以是"""是，用戶休息"""或"""否"""作答。\n\n文字：')
        # 3: Query the application and print the result.
        llm_out = requests.post(MY_HOST_URL, json={
            "text": prompt+f'"""{update.message.text}"""'
        }).json()['result']
    if '是，用戶休息' in llm_out:
        prompt = (
            '你是輔助用戶安排工作時間的助手，'
            f'用戶說：\n"""\n{llm_out}\n"""\n'
            f'現在請使用指定的語言【{user["language"]}】'
            '向準備睡覺或者結束今天的工作的用戶告別')
        # 3: Query the application and print the result.
        llm_out = requests.post(MY_HOST_URL, json={
            "text": prompt+f'"""{update.message.text}"""'
        }).json()['result']
        usertable.update({
            'state': 'resting',
            'todos': ''
        }, User.id == user['id'])
        # history reset at rest
    elif user['state'] == 'new':
        prompt = '判別以下文字是什麼語言，僅指出語言的名稱：'
        # 3: Query the application and print the result.
        llm_out = requests.post(MY_HOST_URL, json={
            "text": prompt+f'"""{update.message.text}"""'
        }).json()['result']
        usertable.update(
            {'language': llm_out, 'state': 'planning'},
            User.id == user['id'])
        prompt = (
            f'你是輔助用戶工作的助手，現在請使用指定的語言【{llm_out}】'
            '詢問用戶今天剩餘的時間打算做些什麼')
        llm_out = requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
    elif user['state'] == 'planning':
        prompt = ('你是一位助手，需要整理提供的文字製作成表格找出待辦項目和時間。'
                    '如果文字不包含待辦項目，寫下"""今天沒有任何待辦項目"""。\n'
                    '\n注意：文字未必包含計劃行動的時間。\n'
                    '\n文字：\n"""\n%s\n"""')
        llm_out = requests.post(MY_HOST_URL, json={
            "text": prompt %(update.message.text)
        }).json()['result']
        if '沒有任何待辦項目' in llm_out:
            prompt = (
                '你是輔助用戶工作的助手，根據留言判斷用戶是否請求幫助，以是"""是，用戶請求幫助"""或"""否"""作答。'
                f'用戶有這樣的留言：\n"""\n{update.message.text}\n"""\n')
            llm_out = requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
            if '是，' in llm_out[:3]:
                prompt = (
                    '你是輔助用戶安排工作時間的助手，'
                    f'用戶有這樣的留言：\n"""\n{update.message.text}\n"""\n'
                    f'現在請使用指定的語言【{user["language"]}】'
                    '向用戶提供意見，如果超過你角色的職責，請介紹你的朋友 OpenAI ChatGPT 給用戶。')
                llm_out = requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
            prompt = f'使用指定的語言【{user["language"]}】詢問我希望什麼時候再聯絡'
            llm_out += '\n'
            llm_out += requests.post(MY_HOST_URL, json={
                "text": prompt}).json()['result'].split(':')[-1].replace('"', '')
            usertable.update({
                'state': 'resting',
                'todos': ''
            }, User.id == user['id'])
            # history reset at rest
            pass
        else:
            prompt = (
                f'你是輔助用戶工作的助手，現在請使用指定的語言【{user["language"]}】'
                f'向用戶再次確認下列工作項目：\n{llm_out}')
            llm_out = requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
            prompt = (
                f'你是記錄用戶工作的記錄儀，現在請使用指定的語言【{user["language"]}】'
                f'詢問用戶接下來將會處理清單上的哪一份工作：\n"""\n{llm_out}\n"""')
            usertable.update({'state': 'pre-work', 'todos': llm_out}, User.id == user['id'])
            llm_out += '\n'
            llm_out += requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
    elif user['state'] == 'pre-work':
        prompt = (
            '你是輔助用戶工作的助手，根據留言判斷用戶是否請求幫助，以是"""是，用戶請求幫助"""或"""否"""作答。'
            f'用戶有這樣的留言：\n"""\n{update.message.text}\n"""\n')
        llm_out = requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
        if '是，' in llm_out[:3]:
            prompt = (
                '你是輔助用戶安排工作時間的助手，'
                f'用戶有這樣的留言：\n"""\n{update.message.text}\n"""\n'
                f'現在請使用指定的語言【{user["language"]}】'
                '向用戶提供意見，如果超過你角色的職責，請介紹你的朋友 OpenAI ChatGPT 給用戶。')
            llm_out = requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
        else:
            prompt = ('你是情報分析師，你的任務是識別出用戶開始做表格中哪一件事情了。\n\n'
                        '用這樣的格式回答：正在進行【睡覺】\n\n已知用戶有這些計劃要做的事情：\n'
                        f'"""\n{user.todos}\n"""\n\n並且用戶說：')
            llm_out = requests.post(MY_HOST_URL, json={
                "text": prompt+f'"""{update.message.text}"""'
            }).json()['result']
            usertable.update({'state': f'working:{llm_out}'}, User.id == user['id'])
            prompt = (
                f'你是輔助用戶安排工作時間的助手，現在請使用指定的語言【{user["language"]}】'
                f'告訴用戶你將會跟進用戶的進度\n參考資料：{llm_out}')
            llm_out += requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
    elif user['state'][:8] == 'working:':
        prompt = (
            '你是輔助用戶安排工作時間的助手，根據留言判斷用戶是否完成了當前的工作，'
            '以布林值"""true"""、"""false"""或"""用戶請求幫助"""回答。'
            f'用戶之前的工作狀態：\n"""\n{user["state"]}\n"""\n'
            f'用戶有這樣的留言：\n"""\n{update.message.text}\n"""\n')
        llm_out = requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
        if '用戶請求幫助' in llm_out:
            prompt = (
                '你是輔助用戶安排工作時間的助手，'
                f'用戶有這樣的留言：\n"""\n{update.message.text}\n"""\n'
                f'現在請使用指定的語言【{user["language"]}】'
                '向用戶提供意見，如果超過你角色的職責，請介紹你的朋友 OpenAI ChatGPT 給用戶。')
            llm_out = requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
        elif 'true' in llm_out.lower():
            prompt = (
                '你是輔助用戶安排工作時間的助手，根據留言判斷用戶接下來要做什麼，'
                '如果用戶已經提出新項目，那麼用這樣的格式回答："""接下來進行【睡覺】"""'
                '如果用戶未有計劃，則回答："""【pre-work】"""\n\n'
                f'用戶原本計劃：\n"""\n{user["state"]}\n"""\n'
                f'用戶現在說：\n"""\n{update.message.text}\n"""\n')
            llm_out = requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
            if 'pre-work' in llm_out:
                usertable.update({'state': 'pre-work'}, User.id == user['id'])
            else:
                usertable.update({'state': f'working:{llm_out}'}, User.id == user['id'])
            # prompt = (
            #     '判斷用戶已經完成了那些項目'
            #     '資料如下：\n```\n'
            #     f'用戶原本計劃：\n"""\n{user["state"]}\n"""\n'
            #     f'用戶現在說：\n"""\n{update.message.text}\n"""\n'
            #     '```\n\n以上是你所需要的資料，現在列出用戶已經完成了的項目')
            # llm_out = requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
            # # 為用戶列出未完成待辦事項作為參考
            # llm_out += f'\n\n待辦事項清單：\n{user.todos}'
            # prompt = (
            #     '你是輔助用戶安排工作時間的助手，根據留言新增或移除待辦事項清單的內容，'
            #     f'用戶原本計劃：\n"""\n{user["state"]}\n"""\n'
            #     f'用戶現在說：\n"""\n{update.message.text}\n"""\n'
            #     f'你認為：\n"""\n{llm_out}\n"""\n'
            #     f'待辦事項清單：\n"""\n{user.todos}\n"""\n'
            #     '寫下新的清單內容，或沒有刪改的話直接重複就可以了。'
            #     )
            # llm_out = requests.post(MY_HOST_URL, json={"text": prompt}).json()['result']
            # # 用戶提出的事情對代辦事項清單有什麼影響？
            # # 現在用戶狀態是什麼，新的代辦事項清單是怎樣的？
            # # 需要將工作分成更細的項目嗎？
        # 要回覆嗎？
    elif user['state'] == 'resting':
        prompt = ('你是一位助手，'
                '需要整理提供的文字製作成表格找出待辦項目和時間。'
                '如果文字不包含待辦項目，寫下"""今天沒有任何待辦項目"""。\n\n'
                '注意：文字未必包含計劃行動的時間。\n\n'
                '文字：n"""\n%s\n"""\n')
        llm_out = requests.post(MY_HOST_URL, json={
            "text": prompt %(update.message.text)
        }).json()['result']
        if '沒有任何待辦項目' in llm_out:
            prompt = ('你是輔助用戶安排工作時間的助手，用戶準備開始工作了嗎？'
                    '或許用戶開始規劃今天要做的事情了嗎？\n用戶輸入：')
            llm_out = requests.post(MY_HOST_URL, json={
                "text": prompt+f'"""{update.message.text}"""'
            }).json()['result']
        else:
            usertable.update({'state': 'planning'}, User.id == user['id'])
            await echo(update, context)
            return None
    # log to csv (user['id'], user['state'], update.message.text, llm_out)
    await update.message.reply_text(llm_out)


app = ApplicationBuilder().token(MY_TG_TOKEN).build()

app.add_handler(CommandHandler("start", hello))
app.add_handler(CommandHandler("help", help_msg))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))


app.run_polling()