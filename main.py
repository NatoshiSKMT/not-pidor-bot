#!/usr/bin/env python3
import yaml
try:
    config = yaml.safe_load(open("config.yml"))
except Exception as e:
    raise ValueError("Create your config.yml via 'cp config.yml.example config.yml && nano config.yml'")

import mysql.connector
db = mysql.connector.connect(host=config['host'], user=config['user'], database=config['database'], password=config['password'])
cursor = db.cursor()

from telegram.ext import Updater, MessageHandler, Filters
updater = Updater(token=config['token'])
updater.start_polling()
dispatcher = updater.dispatcher

from datetime import datetime
import re
import random

def ontext(update, context):
    tg_chat_id = update.message.chat.id
    tg_from_id = update.message.from_user.id
    if config['debug']: print(tg_chat_id, " > ", update.message.text);
    #Saving original a message
    sql = "INSERT INTO `messages` (`text`, `tg_chat_id`, `tg_from_id`, `tg_message_id`, `tg_from_username`) VALUES (%s,%s,%s,%s,%s)"
    cursor.execute(sql, (update.message.text, tg_chat_id, tg_from_id, update.message.message_id, update.message.from_user.username))
    db.commit()
    message_id = cursor.lastrowid

    clear_text = re.sub("[^а-яА-Я- ?+]+", "", update.message.text).lower()

    #Personal replies
    #check personal timeout
    last_user_inter = last_interaction(tg_chat_id, tg_from_id)
    if last_user_inter['seconds'] > config['timeout_personal']:
        for reaction in config['reactions']:
            if reaction['prob'] >= random.randrange(100):
                do_reaction = False
                if reaction['where'] == 'end':
                    for pattern in reaction['pattern']:
                        if clear_text.endswith(pattern):
                            do_reaction = True
                elif reaction['where'] == 'full':
                    for pattern in reaction['pattern']:
                        if clear_text == pattern:
                            do_reaction = True
                elif reaction['where'] == 'begin':
                    for pattern in reaction['pattern']:
                        if clear_text.find(pattern) == 0:
                            do_reaction = True
                elif reaction['where'] == 'any':
                    for pattern in reaction['pattern']:
                        if clear_text.find(pattern) >= 0:
                            do_reaction = True
                if do_reaction:
                    reply_text = random.choice(reaction['reply'])
                    update.message.reply_text(reply_text, quote = True)
                    save_reply(reaction['type'], reply_text, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                    return

    #Init chat replies
    last_inter = last_interaction(tg_chat_id)
    if last_inter['seconds'] > config['timeout_chat']:
        #never use this chat
        if(last_inter['seconds'] == 1000000000):
            sql = "SELECT COUNT(*) FROM `messages` WHERE `tg_chat_id` = %s"
            for result in cursor.execute(sql, (tg_chat_id,), multi=True):
                records = cursor.fetchall()
                for row in records:
                    if row[0] < config['first_message_wait']:
                        return
        if last_inter['seconds'] < 1000000000 and last_inter['messages'] > config['replies_frequency']:
            for initreaction in config['initreaction']:
                if initreaction['prob'] >= random.randrange(100):
                    clear_text = re.sub("[^а-яА-Я- ]+", "", clear_text) #romove '?' '+'
                    for word in clear_text.split():
                        replay_word = find_plural(word);
                        if replay_word != False:
                            reply_text = replay_word.title() + ' ' + initreaction['text'];
                            update.message.reply_text(reply_text, quote = True)
                            save_reply(1, reply_text, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                            return

def admin(update, context):
    for item in update.message.text.split():
        item = item.lower()
        replay_word = find_plural(item);
        if replay_word != False:
            chat_id = update.effective_chat.id
            update.message.reply_text(replay_word.title() + ' для пидоров', quote = True)

#Find plural form of word
def find_plural(word):
    plural = False
    if len(word) <= 3: return plural
    startTime = datetime.now()
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

# Save replies to DB
def save_reply(type, text, message_id, tg_chat_id, tg_from_id, tg_message_id):
    sql = "INSERT INTO `replies` (`type`, `message_id`, `text`, `tg_chat_id`, `tg_from_id`, tg_message_id) VALUES (%s,%s,%s,%s,%s,%s)"
    cursor.execute(sql, (type, message_id, text, tg_chat_id, tg_from_id,tg_message_id))
    db.commit()

# Return seconds till last interaction
def last_interaction(tg_chat_id, tg_from_id = 0, type = 0):
    res = {'seconds' : 1000000000, 'messages' : 1000000000}
    #time
    sql = "SELECT TIMESTAMPDIFF(SECOND,date,CURRENT_TIMESTAMP) as diff, tg_message_id FROM `replies` WHERE `tg_chat_id` = %s"
    params = (tg_chat_id,)
    if tg_from_id !=0 :
        sql += ' AND `tg_from_id` = %s'
        params += (tg_from_id,)
    if type !=0 :
        sql += ' AND `type` = %s'
        params += (type,)
    sql += ' ORDER BY `id` DESC LIMIT 1'
    for result in cursor.execute(sql, params, multi=True):
        records = cursor.fetchall()
        for row in records:
            res['seconds'] = row[0]
            last_reply_tg_id = row[1]
            #messages count
            sql = "SELECT `tg_message_id` FROM `messages` WHERE `tg_chat_id` = %s ORDER BY `id` DESC LIMIT 1"
            params = (tg_chat_id,)
            for result in cursor.execute(sql, params, multi=True):
                records = cursor.fetchall()
                for row in records:
                    res['messages'] = row[0] - last_reply_tg_id
    return res

if config['admin_chat_id'] > 0:
    admin_handler = MessageHandler(Filters.chat(config['admin_chat_id']), admin)
    dispatcher.add_handler(admin_handler)

text_handler = MessageHandler(Filters.text & (~Filters.command), ontext)
dispatcher.add_handler(text_handler)
