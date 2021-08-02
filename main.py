#!/usr/bin/env python3
import yaml
try:
    config = yaml.safe_load(open("config.yml"))
except Exception as e:
    raise ValueError("Create your config.yml via 'cp config.yml.example config.yml && nano config.yml'")

import mysql.connector
db = mysql.connector.connect(
    host=config['host'],
    user=config['user'],
    database=config['database'],
    password=config['password']
)
cursor = db.cursor()

from telegram.ext import Updater, MessageHandler, Filters
updater = Updater(token=config['token'])
updater.start_polling()
dispatcher = updater.dispatcher

from datetime import datetime
import re

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

def pidor(update, context):
    #Saving a message
    sql = "INSERT INTO `messages` (`text`, `tg_chat_id`, `tg_from_id`, `tg_from_username`) VALUES (%s, %s, %s, %s)"
    cursor.execute(sql, (update.message.text, update.message.chat.id, update.message.from_user.id, update.message.from_user.username))
    db.commit()
    message_id = cursor.lastrowid

    #Static replies
    #check personal timeout
    ###...

    clear_text = re.sub("[^a-zA-Zа-яА-Я- ]+", "", update.message.text).lower()

    if clear_text.endswith('для пидоров'):
        update.message.reply_text('+', quote = True)
        return

    for word in clear_text.split():
        replay_word = find_plural(word);
        if replay_word != False:
            chat_id = update.effective_chat.id
            update.message.reply_text(replay_word.title() + ' для пидоров', quote = True)
            return

def admin(update, context):
    for item in update.message.text.split():
        item = item.lower()
        replay_word = find_plural(item);
        if replay_word != False:
            chat_id = update.effective_chat.id
            update.message.reply_text(replay_word.title() + ' для пидоров', quote = True)

if config['admin_chat_id'] > 0:
    admin_handler = MessageHandler(Filters.chat(config['admin_chat_id']), admin)
    dispatcher.add_handler(admin_handler)

pidor_handler = MessageHandler(Filters.text & (~Filters.command), pidor)
dispatcher.add_handler(pidor_handler)
