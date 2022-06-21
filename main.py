#!/usr/bin/env python3
import yaml
import mysql.connector
import re
import random
import logging
from telegram.ext import Updater, MessageHandler, Filters
from datetime import datetime, timezone

import pytesseract
import cv2


# Set up the logger
logging.basicConfig(
    level=logging.INFO,
    # level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Loading configuration
try:
    config = yaml.safe_load(open("config.yml"))
except Exception:
    logger.exception("Fail to open config.yml")
    exit()
else:
    logger.info("Configuration loaded from config.yml")

# Connect to database
try:
    db = mysql.connector.connect(
        host=config['host'],
        user=config['user'],
        database=config['database'],
        password=config['password']
    )
    db.ping(reconnect=True, attempts=100, delay=1)
    cursor = db.cursor(dictionary=True)

except Exception:
    logger.exception("Database connection error")
    exit()
else:
    logger.info("Database connected")

# Run telegram bot
try:
    updater = Updater(token=config['token'])
    updater.start_polling()
    # updater.idle()
    dispatcher = updater.dispatcher
except Exception:
    logger.exception("Bot is NOT running")
    exit()
else:
    logger.info("Bot is running")


class Chat():
    """Class for operate with telegram chats."""
    def __init__(self, tg_chat_id):
        super(Chat, self).__init__()
        self.tg_chat_id = tg_chat_id
        self.msg_after_reply = 0  # message counet
        self.last_message = self.get_last_message()  # Last received message
        self.last_reply = self.get_last_reply()  # Last bot replay
        self.title = "None"

        # No replies in this chat
        if self.last_reply is None:
            self.last_reply = {}
            self.last_reply['date'] = datetime.now(timezone.utc)
            self.last_reply['tg_from_id'] = 0
            logger.debug("No replies in this chat")
        else:
            self.msg_after_reply = self.msg_count(self.last_reply['message_id'])

    def save_reply(self, type, text, tg_from_id, tg_message_id):
        sql = "INSERT INTO `replies` (`type`, `message_id`, `text`, `tg_chat_id`, `tg_from_id`, tg_message_id) VALUES (%s,%s,%s,%s,%s,%s)"
        cursor.execute(sql, (
            type, self.last_message['id'], text, self.tg_chat_id,
            tg_from_id, tg_message_id)
        )
        db.commit()
        self.last_reply['message_id'] = self.last_message['id']
        self.last_reply['type'] = type
        self.last_reply['tg_from_id'] = tg_from_id
        self.last_reply['date'] = datetime.now(timezone.utc)
        self.msg_after_reply = 0
        
        # send message to admin
        updater.bot.send_message(config['admin_chat_id'], self.last_message['text'], parse_mode="Markdown")

    def get_last_reply(self):
        sql = """
            SELECT
                `message_id`,
                `type`,
                `tg_from_id`,
                CONVERT_TZ(`date`, @@session.time_zone, '+00:00') as date
            FROM `replies`
            WHERE
                `tg_chat_id` = %s
            ORDER BY `id` DESC LIMIT 1
        """
        cursor.execute(sql, (self.tg_chat_id,))

        row = cursor.fetchone()
        if row is not None:
            return row
        else:
            return None

    def save_message(self, text, tg_from_id, tg_message_id, username):
        sql = """
            INSERT INTO `messages`
                (`text`, `tg_chat_id`, `tg_from_id`, `tg_message_id`,
                `tg_from_username`)
            VALUES (%s,%s,%s,%s,%s)
        """
        cursor.execute(
            sql, (text, self.tg_chat_id, tg_from_id, tg_message_id, username)
        )
        db.commit()
        self.last_message['id'] = int(cursor.lastrowid)
        self.last_message['text'] = text
        self.last_message['tg_from_id'] = tg_from_id
        self.last_message['tg_message_id'] = tg_message_id
        self.last_message['username'] = username
        self.msg_after_reply += 1

    def get_last_message(self):
        sql = """
            SELECT * FROM `messages`
            WHERE `tg_chat_id` = %s ORDER BY `id` DESC LIMIT 1
        """
        cursor.execute(sql, (self.tg_chat_id,))

        row = cursor.fetchone()
        if row is not None:
            return row
        else:
            return {}

    def msg_count(self, message_id):
        sql = """
            SELECT COUNT(*) as `count` FROM `messages`
            WHERE
                `tg_chat_id` = %s
                AND `id` > %s
        """
        cursor.execute(sql, (self.tg_chat_id, message_id,))
        row = cursor.fetchone()
        if row is not None:
            return row['count']
        else:
            return 0

    def msg_after_r(self):
        return self.msg_after_reply

    def sec_after_r(self):
        date = self.last_reply['date'].replace(tzinfo=timezone.utc)
        return round((datetime.now(timezone.utc) - date).total_seconds())


def onsticker(update, context):
    '''
    Receive a sticker, reply telegram file_id
    '''
    # ADMIN only:
    if update.message.chat.id == config['admin_chat_id']:
        update.message.reply_text(update.message.sticker.file_id)
        logger.info(f"ADMIN onsticker: {update.message.sticker.file_id}")


def ontext(update, context, text=None):
    """
    Processing all patterns on text messages
    """
    # Ignore edited message
    if not update.message:
        logger.debug("Edited message ignored")
        return

    # Ignore old messages
    if (datetime.now(timezone.utc) - update.message.date).total_seconds() > 5:
        logger.debug("Old message ignored")
        return

    if text is None:
        text = update.message.text

    tg_chat_id = update.message.chat.id
    tg_from_id = update.message.from_user.id
    logger.info("{}({}), {}({}): {}".format(
        update.message.chat.title, tg_chat_id,
        update.message.from_user.username, tg_from_id, text
    ))

    if tg_chat_id not in Chats:
        current_chat = Chat(tg_chat_id)
        current_chat.title = update.message.chat.title
        Chats[tg_chat_id] = current_chat
    else:
        current_chat = Chats[tg_chat_id]

    # Saving original a message
    current_chat.save_message(
        text, tg_from_id, update.message.message_id,
        update.message.from_user.username
    )

    clear_text = re.sub("[^а-яА-Я- ?+]+", "", text).lower()

    # Reply on patterns config['patterns']
    logger.debug('Reply on patterns...')
    # Check personal timeout
    personal_timer = 0
    personal_timer_type = 0
    if current_chat.last_reply['tg_from_id'] == tg_from_id:
        personal_timer = config['timeout_personal'] - current_chat.sec_after_r()
        if personal_timer < config['timeout_personal']:
            personal_timer_type = current_chat.last_reply['type']

    logger.debug(f"Сhat timers: {current_chat.msg_after_r()} msg,  {current_chat.sec_after_r()} sec")

    for reaction in config['patterns']:
        if personal_timer_type == reaction['type'] and personal_timer > 0:
            logger.debug(f"Personal timeout {config['timeout_personal'] - personal_timer} s.")
            continue

        # Saving throw via reaction['prob']
        if tg_chat_id == config['admin_chat_id']:
            reaction['prob'] = 100
        if (reaction['prob'] * 100 < random.randrange(10000)):
            logger.debug(f"Saving throw: {reaction['prob']}%")
            logger.debug(reaction)
            continue

        # Where is the pattern?
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

        if do_reaction is True:
            # Replay / replay on replay / just text - replay_to_parent
            reply_to_message_id = update.message.message_id
            if 'replay_to_parent' in reaction:
                if update.message.reply_to_message:
                    reply_to_message_id = update.message.reply_to_message.message_id
                else:
                    logger.debug("Parent message required.")
                    continue
            elif "no_replay" in reaction:
                reply_to_message_id = 0
            # Replying via reply_type
            if reaction['reply_type'] == 'text':
                reply_text = random.choice(reaction['reply'])
                update.message.reply_text(reply_text, reply_to_message_id=reply_to_message_id)
                current_chat.save_reply(
                    reaction['type'], reply_text,
                    tg_from_id, update.message.message_id)
                logger.info(f"REPLY: {reply_text}")
                return
            elif reaction['reply_type'] == 'video':
                fname = './' + random.choice(reaction['reply'])
                update.message.reply_video(video=open(fname, 'rb'), supports_streaming=True, reply_to_message_id=reply_to_message_id)
                current_chat.save_reply(
                    reaction['type'], fname,
                    tg_from_id, update.message.message_id)
                logger.info(f"REPLY: {fname}")
                return
            elif reaction['reply_type'] == 'photo':
                fname = './' + random.choice(reaction['reply'])
                update.message.reply_photo(photo=open(fname, 'rb'), caption=reaction['caption'], reply_to_message_id=reply_to_message_id)
                current_chat.save_reply(
                    reaction['type'], fname,
                    tg_from_id, update.message.message_id)
                logger.info(f"REPLY: {fname}")
                return
            elif reaction['reply_type'] == 'voice':
                fname = './' + random.choice(reaction['reply'])
                update.message.reply_voice(voice=open(fname, 'rb'), reply_to_message_id=reply_to_message_id)
                current_chat.save_reply(
                    reaction['type'], fname,
                    tg_from_id, update.message.message_id)
                logger.info(f"REPLY: {fname}")
                return
            elif reaction['reply_type'] == 'sticker':
                sticker = random.choice(reaction['reply'])
                update.message.reply_sticker(sticker=sticker, reply_to_message_id=reply_to_message_id)
                current_chat.save_reply(
                    reaction['type'], sticker,
                    tg_from_id, update.message.message_id)
                logger.info(f"REPLY: {sticker}")
                return

    logger.debug('Personal reply pattern is not found')

    # Сhat reaction on any text. config['reactions']
    logger.debug('Сhat reaction...')

    # Check chat timeouts
    if current_chat.sec_after_r() < config['timeout_chat']:
        logger.debug(f"Chat timeout {config['timeout_chat'] - current_chat.sec_after_r()} s.")
        return
    if current_chat.msg_after_r() < config['replies_frequency']:
        logger.debug(f"Chat timeout {config['replies_frequency'] - current_chat.msg_after_r()} msgs.")
        return

    for reaction in config['reactions']:
        # Saving throw via reaction['prob']
        if tg_chat_id == config['admin_chat_id']:
            reaction['prob'] = 100
        if (reaction['prob'] * 100 < random.randrange(10000)):
            logger.debug(f"Saving throw: {reaction['text']} - {reaction['prob']}%")
            continue

        # Try to genegate answer
        clear_text = re.sub("[^а-яА-Я- ]+", "", clear_text)  # del '?' '+'
        for word in clear_text.split():
            # Ignore short words
            if len(word) <= 3:
                continue

            word_forms = get_word(word)
            if word_forms is None:
                continue

            reply_text = reaction['text']
            for word_form in word_forms:
                # Plural form
                if word_form['plural'] == 1:
                    reply_text = reply_text.replace(
                        "..множ..", word_form['word']
                    )
                # Case forms
                else:
                    reply_text = reply_text.replace(
                        f"..{word_form['wcase']}..", word_form['word']
                    )
            if reply_text.find("..") >= 0:
                # logger.warning("Fail to replace all ..[form]..", reply_text)
                continue
            reply_text = reply_text[0].upper() + reply_text[1:]
            update.message.reply_text(reply_text, quote=True)
            
            # save replay to DB
            current_chat.save_reply(
                1, reply_text,
                tg_from_id, update.message.message_id)
            logger.info(f"REPLY: {reply_text}")
            return
    logger.debug('No chat reaction')


def onjoin(update, context):
    # TODO: Move to config
    sticker = "CAACAgUAAxkBAALRYmFMKSIKA6MuLhAJ2l05uZi-v5PqAAL5BAACAethVuvtZALvfe75IQQ"
    # logger.info(update.message.new_chat_members[0].id)
    if update.message.new_chat_members[0].id == 982289358:  # лось
        update.message.reply_sticker(sticker=sticker)
        logger.info(f"REPLY: {sticker}")


def onphoto(update, context):
    # check photo
    if update.message.photo is None:
        logger.error("Photo is None")
        logger.error(update.message.photo)
        return
    
    file = context.bot.getFile(update.message.photo[-1].file_id)
    tg_chat_id = update.message.chat.id
    tg_from_id = update.message.from_user.id
    # path = file.download(f'img/{tg_chat_id}/{tg_from_id}/jopa.jpg')
    path = file.download(f'img/{tg_chat_id}_{tg_from_id}_{file.file_unique_id}.jpg')
    image = cv2.imread(path)
    string = pytesseract.image_to_string(image, lang="rus")
    if len(re.sub("[^а-яА-Я]+", "", string)):
        string = re.sub("[^а-яА-Я- ]+", "", string)
        ontext(update, context, f'[OCR] {re.sub("[^а-яА-Я- ]+", "", string)}')


def get_word(word):
    if len(word) <= 3:
        return None

    sql = "SELECT * FROM `nouns_morf` WHERE `word` = %s LIMIT 1"
    cursor.execute(sql, (word,))

    founded_form = cursor.fetchone()
    if founded_form is None:
        return None  # word not found

    if founded_form['code_parent'] == 0:
        wordcode = founded_form['code']  # subjective case
    else:
        wordcode = founded_form['code_parent']

    sql = """
        SELECT * FROM `nouns_morf`
        WHERE
            `code_parent` = %s
            OR `code` = %s
    """
    for result in cursor.execute(sql, (wordcode, wordcode,), multi=True):
        result = cursor.fetchall()
        return result
    return None


Chats = {}


def main():
    if config['admin_chat_id'] > 0:
        admin_handler = MessageHandler(
            Filters.chat(config['admin_chat_id']) & Filters.text & (~Filters.command),
            ontext
        )
        dispatcher.add_handler(admin_handler)

    text_handler = MessageHandler(Filters.text & (~Filters.command), ontext)
    dispatcher.add_handler(text_handler)

    sticker_handler = MessageHandler(Filters.sticker, onsticker)
    dispatcher.add_handler(sticker_handler)

    join_handler = MessageHandler(Filters.status_update.new_chat_members, onjoin)
    dispatcher.add_handler(join_handler)

    image_handler = MessageHandler(Filters.photo, onphoto)
    dispatcher.add_handler(image_handler)


if __name__ == '__main__':
    main()
