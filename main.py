import time
import schedule
from bot_active import job
# import bot_passive

schedule.every().hour.do(job)

while True:
    schedule.run_pending()
    time.sleep(600)