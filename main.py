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

from datetime import datetime, timezone
import re
import random

def onsticker(update, context):
    if update.message.chat.id == config['admin_chat_id']:
        update.message.reply_text(update.message.sticker.file_id)

def ontext(update, context):
    #ignore edited message
    if not update.message: return
    #ignore old
    if (datetime.now(timezone.utc)-update.message.date).total_seconds() > 5: return

    tg_chat_id = update.message.chat.id
    tg_from_id = update.message.from_user.id
    if config['debug']: print(tg_chat_id, " > ", update.message.text);
    #load interaction data before saving
    last_user_inter = last_interaction(tg_chat_id, tg_from_id)
    last_inter = last_interaction(tg_chat_id)
    #Saving original a message
    sql = "INSERT INTO `messages` (`text`, `tg_chat_id`, `tg_from_id`, `tg_message_id`, `tg_from_username`) VALUES (%s,%s,%s,%s,%s)"
    cursor.execute(sql, (update.message.text, tg_chat_id, tg_from_id, update.message.message_id, update.message.from_user.username))
    db.commit()
    message_id = cursor.lastrowid

    clear_text = re.sub("[^а-яА-Я- ?+]+", "", update.message.text).lower()

    #Personal replies
    #check personal timeout
    if last_user_inter['seconds'] > config['timeout_personal'] or tg_chat_id == config['admin_chat_id']:
        if config['debug']: print('Personal reply...')
        for reaction in config['reactions']:
            if reaction['prob'] >= random.randrange(100) or tg_chat_id == config['admin_chat_id']:
                do_reaction = False
                #whe is the pattern
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
                    #replay on trigger message / on message trigger was replyed / just text to chat
                    reply_to_message_id = update.message.message_id
                    if 'replay_to_parent' in reaction:
                        if update.message.reply_to_message:
                            reply_to_message_id = update.message.reply_to_message.message_id
                        else:
                            if config['debug']: print('No parent message. replay_to_parent')
                            return
                    elif "no_replay" in reaction:
                        reply_to_message_id = 0
                    if reaction['reply_type'] == 'text':
                        reply_text = random.choice(reaction['reply'])
                        update.message.reply_text(reply_text, reply_to_message_id = reply_to_message_id)
                        save_reply(reaction['type'], reply_text, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                        if config['debug']: print('REPLY: ', reply_text)
                        return
                    elif reaction['reply_type'] == 'video':
                        fname = './' + random.choice(reaction['reply'])
                        update.message.reply_video(video=open(fname, 'rb'), supports_streaming=True, reply_to_message_id = reply_to_message_id)
                        save_reply(reaction['type'], fname, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                        if config['debug']: print('REPLY: ', fname)
                        return
                    elif reaction['reply_type'] == 'photo':
                        fname = './' + random.choice(reaction['reply'])
                        update.message.reply_photo(photo=open(fname, 'rb'), caption=reaction['caption'], reply_to_message_id = reply_to_message_id)
                        save_reply(reaction['type'], fname, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                        if config['debug']: print('REPLY: ', fname)
                        return
                    elif reaction['reply_type'] == 'voice':
                        fname = './' + random.choice(reaction['reply'])
                        update.message.reply_voice(voice=open(fname, 'rb'), reply_to_message_id = reply_to_message_id)
                        save_reply(reaction['type'], fname, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                        if config['debug']: print('REPLY: ', fname)
                        return
                    elif reaction['reply_type'] == 'sticker':
                        sticker = random.choice(reaction['reply'])
                        update.message.reply_sticker(sticker = sticker, reply_to_message_id = reply_to_message_id)
                        save_reply(reaction['type'], sticker, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                        if config['debug']: print('REPLY: ', sticker)
                        return
    elif config['debug']: print("Personal replies...", last_user_inter)

    #Init chat replies
    #check chat timeout
    if last_inter['seconds'] > config['timeout_chat']:
        if config['debug']: print('Chat reply...')
        #never use this chat
        if(last_inter['seconds'] == 1000000000):
            sql = "SELECT COUNT(*) FROM `messages` WHERE `tg_chat_id` = %s"
            for result in cursor.execute(sql, (tg_chat_id,), multi=True):
                records = cursor.fetchall()
                for row in records:
                    if row[0] < config['first_message_wait']:
                        if config['debug']: print('first_message_wait timeout')
                        return
        if last_inter['seconds'] < 1000000000 and (last_inter['messages'] > config['replies_frequency'] or last_inter['messages'] < 0):
            for initreaction in config['initreaction']:
                if initreaction['prob'] >= random.randrange(100) or tg_chat_id == config['admin_chat_id']:
                    clear_text = re.sub("[^а-яА-Я- ]+", "", clear_text) #romove '?' '+'
                    for word in clear_text.split():
                        replay_word = find_plural(word);
                        if replay_word != False:
                            reply_text = replay_word.title() + ' ' + initreaction['text'];
                            update.message.reply_text(reply_text, quote = True)
                            save_reply(1, reply_text, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                            if config['debug']: print('REPLY: ', reply_text)
                            return
                elif config['debug']: print('probably fail for', initreaction)
        elif config['debug']: print('waiting for a chat timeout 2...', last_inter)
    elif config['debug']: print('waiting for a chat timeout 1...', last_inter)
    if config['debug']: print('No reply found');
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
    admin_handler = MessageHandler(Filters.chat(config['admin_chat_id']) & Filters.text & (~Filters.command), ontext)
    dispatcher.add_handler(admin_handler)

text_handler = MessageHandler(Filters.text & (~Filters.command), ontext)
dispatcher.add_handler(text_handler)

sticker_handler = MessageHandler(Filters.sticker, onsticker)
dispatcher.add_handler(sticker_handler)
