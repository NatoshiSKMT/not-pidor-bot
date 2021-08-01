#!/usr/bin/env python3
import yaml
try:
    config = yaml.safe_load(open("fconfig.yml"))
except Exception as e:
    raise ValueError("Create your config.yml via 'cp config.yml.example config.yml && nano config.yml'")

import mysql.connector
mydb = mysql.connector.connect(
    host=config['host'],
    user=config['user'],
    database=config['database'],
    password=config['password']
)
cursor = mydb.cursor()

from telegram.ext import Updater
updater = Updater(token=config['token'])
updater.start_polling()
dispatcher = updater.dispatcher

from datetime import datetime

def find_plural(word):
    startTime = datetime.now()
    plural = False
    sql = "SELECT * FROM `nouns_morf` WHERE `word` = %s LIMIT 1"
    for result in cursor.execute(sql, (word,), multi=True):
        records = cursor.fetchall()
        for row in records:
            wordcode = 0
            if row[3] == 0: wordcode = row[2] #именительный падеж
            else: wordcode = row[3] #другой падеж
            sql = "SELECT * FROM `nouns_morf` WHERE (`code_parent` = %s OR `code` = %s) AND `plural` = 1 AND `wcase` = 'им' LIMIT 1"
            for result in cursor.execute(sql, (wordcode,wordcode,), multi=True):
                records = cursor.fetchall()
                for row in records:
                    plural = row[1]
    print("SEARCH: " + word + " {}".format(datetime.now() - startTime))
    return plural

def echo(update, context):
    for item in update.message.text.split():
        item = item.lower()
        replay_word = find_plural(item);
        if replay_word != False:
            #chat_id = update.effective_chat.id
            chat_id = 127529747
            context.bot.send_message(chat_id, text = replay_word.title() + ' для пидоров')

from telegram.ext import MessageHandler, Filters
echo_handler = MessageHandler(Filters.text & (~Filters.command), echo)
dispatcher.add_handler(echo_handler)
