#!/usr/bin/env python3
import yaml
import mysql.connector
import re
import random
import logging
from telegram.ext import Updater, MessageHandler, Filters
from datetime import datetime, timezone

# Set up the logger
logging.basicConfig(
    level=logging.INFO,
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
    dispatcher = updater.dispatcher
except Exception:
    logger.exception("Bot is NOT running")
    exit()
else:
    logger.info("Bot is running")


class User():
    """Class for operate with telegram users."""
    def __init__(self, tg_user_id):
        super(Chat, self).__init__()
        self.tg_user_id = tg_user_id
        self.last_reaction_date = datetime.now(timezone.utc)
        self.last_reaction = None


class Chat():
    """Class for operate with telegram chats."""
    def __init__(self, tg_chat_id):
        super(Chat, self).__init__()
        self.tg_chat_id = tg_chat_id
        self.msg_after_reply = 0  # message counet
        self.last_message = self.get_last_message()  # Last received message
        self.last_reply = self.get_last_reply()  # Last bot replay

        # No replies in this chat
        if self.last_reply is None:
            self.last_reply = {}
            self.last_reply['date'] = datetime.now(timezone.utc)
            logger.debug("No replies in this chat")

    def get_last_reply(self):
        sql = """
            SELECT * FROM `replies`
            WHERE `tg_chat_id` = %s ORDER BY `id` DESC LIMIT 1
        """
        cursor.execute(sql, (self.tg_chat_id,))

        row = cursor.fetchone()
        if row is not None:
            return row
        else:
            return None

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
            return None

    def msg_count(self, message_id):
        sql = """
            SELECT COUNT(*) as `count` FROM `messages`
            WHERE `tg_chat_id` = %s AND `id` > %s
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

    def seconds_after_reply(self, message_id):
        sql = """SELECT TIMESTAMPDIFF(SECOND,date,CURRENT_TIMESTAMP) as diff, type
                 FROM `replies`
                 WHERE
                    tg_chat_id = %s
                    AND message_id = %s
                 ORDER BY `id` DESC LIMIT 1"""
        cursor.execute(sql, (self.tg_chat_id, message_id,))
        row = cursor.fetchone()
        if row is not None:
            self.reply_type = row[1]
            return row[0]
        else:
            logger.warning("Given inexistent message_id")
            return -1

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
        self.last_message['id'] = cursor.lastrowid
        self.last_message['text'] = text
        self.last_message['tg_from_id'] = tg_from_id
        self.last_message['tg_message_id'] = tg_message_id
        self.last_message['username'] = username
        logger.debug(f"Message saved to BD id: {self.last_message['id']}")
        self.msg_after_reply += 1

    def save_reply(self, type, text, tg_chat_id, tg_from_id, tg_message_id):
        sql = "INSERT INTO `replies` (`type`, `message_id`, `text`, `tg_chat_id`, `tg_from_id`, tg_message_id) VALUES (%s,%s,%s,%s,%s,%s)"
        cursor.execute(sql, (
            type, self.last_message['id'], text, self.tg_chat_id,
            tg_from_id, tg_message_id)
        )
        db.commit()
        self.last_reply['date'] = datetime.now(timezone.utc)


def onsticker(update, context):
    '''
    Receive a sticker, returns telegram file_id
    '''
    # ADMIN: echo trlegram file_id for sticker
    if update.message.chat.id == config['admin_chat_id']:
        update.message.reply_text(update.message.sticker.file_id)
        logger.info(f"ADMIN onsticker: {update.message.sticker.file_id}")


def ontext(update, context):
    """
    Processing all reactions on text messages
    """
    # Ignore edited message
    if not update.message:
        logger.debug("Edited message ignored")
        return

    # Ignore old messages
    if (datetime.now(timezone.utc) - update.message.date).total_seconds() > 5:
        logger.debug("Old message ignored")
        return

    tg_chat_id = update.message.chat.id
    tg_from_id = update.message.from_user.id
    logger.debug("{}({}), {}({}): {}".format(
        update.message.chat.title, tg_chat_id,
        update.message.from_user.username, tg_from_id, update.message.text
    ))

    if tg_chat_id not in Chats:
        Chats[tg_chat_id] = Chat(tg_chat_id)
    current_chat = Chats[tg_chat_id]

    # Saving original a message
    current_chat.save_message(
        update.message.text, tg_from_id,
        update.message.message_id,
        update.message.from_user.username
    )

    print(f"msg: {current_chat.msg_after_r()}  sec: {current_chat.sec_after_r()}")

    clear_text = re.sub("[^а-яА-Я- ?+]+", "", update.message.text).lower()

    # Сhat replies on any text. config['reaction']
    # TODO: Check chat timeouts

    # if config['timeout_chat'] & config['replies_frequency']
    for reaction in config['reaction']:
        # Saving throw via reaction['prob']
        if tg_chat_id == config['admin_chat_id']:
            reaction['prob'] = 100
        if (reaction['prob'] * 100 < random.randrange(10000)):
            logger.debug(f"Saving throw: {reaction['text']} - {reaction['prob']}%")
            continue

        # Try to genegate answer
        clear_text = re.sub("[^а-яА-Я- ]+", "", clear_text)  # del '?' '+'
        for word in clear_text.split():
            # TODO: ::plural:: and more
            replay_word = find_plural(word)
            if replay_word is not None:
                reply_text = reaction['text'].replace(
                    ".мн.", replay_word.title()
                )
                update.message.reply_text(reply_text, quote=True)
                current_chat.save_reply(
                    1, reply_text,
                    tg_chat_id, tg_from_id, update.message.message_id)
                logger.info(f"REPLY: {reply_text}")
                return


    #logger.debug(f"Chat timeout 2. Waiting for {config['timeout_chat'] - last_inter['seconds']} s.")
    #else: logger.debug(f"Chat timeout 1. Waiting for {config['timeout_chat'] - last_inter['seconds']} s.")



    # if row[0] < config['first_message_wait']:
    #        logger.debug('Waiting for first_message_wait timeout')
    #        return

    '''
    # Personal replies on patterns. config['reactions']
    if current_chat.personal_timeout(tg_from_id):



    # check personal timeout
    if last_user_inter['seconds'] > config['timeout_personal'] or tg_chat_id == config['admin_chat_id']:
        logger.debug("Personal reply...")
        for reaction in config['reactions']:
            if reaction['prob'] * 100 >= random.randrange(10000) or tg_chat_id == config['admin_chat_id']:
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
                            logger.debug("No parent message. replay_to_parent")
                            return
                    elif "no_replay" in reaction:
                        reply_to_message_id = 0
                    if reaction['reply_type'] == 'text':
                        reply_text = random.choice(reaction['reply'])
                        update.message.reply_text(reply_text, reply_to_message_id = reply_to_message_id)
                        save_reply(reaction['type'], reply_text, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                        logger.info(f"REPLY: {reply_text}")
                        return
                    elif reaction['reply_type'] == 'video':
                        fname = './' + random.choice(reaction['reply'])
                        update.message.reply_video(video=open(fname, 'rb'), supports_streaming=True, reply_to_message_id = reply_to_message_id)
                        save_reply(reaction['type'], fname, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                        logger.info(f"REPLY: {fname}")
                        return
                    elif reaction['reply_type'] == 'photo':
                        fname = './' + random.choice(reaction['reply'])
                        update.message.reply_photo(photo=open(fname, 'rb'), caption=reaction['caption'], reply_to_message_id = reply_to_message_id)
                        save_reply(reaction['type'], fname, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                        logger.info(f"REPLY: {fname}")
                        return
                    elif reaction['reply_type'] == 'voice':
                        fname = './' + random.choice(reaction['reply'])
                        update.message.reply_voice(voice=open(fname, 'rb'), reply_to_message_id = reply_to_message_id)
                        save_reply(reaction['type'], fname, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                        logger.info(f"REPLY: {fname}")
                        return
                    elif reaction['reply_type'] == 'sticker':
                        sticker = random.choice(reaction['reply'])
                        update.message.reply_sticker(sticker = sticker, reply_to_message_id = reply_to_message_id)
                        save_reply(reaction['type'], sticker, message_id, tg_chat_id, tg_from_id, update.message.message_id);
                        logger.info(f"REPLY: {sticker}")
                        return
    else:
        logger.debug(f"Personal timeout. Waiting for {config['timeout_personal'] - last_user_inter['seconds']} s.")

    logger.debug('No reply found');
    '''


# Find plural form of word
def find_plural(word):
    plural = None
    if len(word) <= 3:
        return plural
    startTime = datetime.now()
    sql = "SELECT * FROM `nouns_morf` WHERE `word` = %s LIMIT 1"
    for result in cursor.execute(sql, (word,), multi=True):
        records = cursor.fetchall()
        for row in records:
            wordcode = 0
            if row['code_parent'] == 0:
                wordcode = row['code']  # нашли сразу именительный падеж
            else:
                wordcode = row['code_parent']
            sql = """
                SELECT * FROM `nouns_morf`
                WHERE
                    (`code_parent` = %s OR `code` = %s)
                    AND `plural` = 1 AND `wcase` = 'им'
                LIMIT 1
            """
            for result in cursor.execute(sql, (wordcode, wordcode,), multi=True):
                records = cursor.fetchall()
                for row in records:
                    plural = row['word']
    logger.info(f"Plural form: {word} is {plural} {datetime.now() - startTime}")
    return plural


def last_replay_to_user(tg_chat_id, tg_from_id):
    res = {'seconds' : 0, 'type' : 0}
    sql = """SELECT TIMESTAMPDIFF(SECOND,date,CURRENT_TIMESTAMP) as diff, type
             FROM `replies`
             WHERE `tg_chat_id` = %s AND `tg_from_id` = %s
             ORDER BY `id` DESC LIMIT 1"""
    params = (tg_chat_id,tg_from_id,)
    for result in cursor.execute(sql, params, multi=True):
        records = cursor.fetchall()
        for row in records:
            res['seconds'] = row[0]
            res['type'] = row[1]
    return res

def last_replay_in_chat(tg_chat_id):
    res = {'seconds' : 0, 'messages' : 0}
    sql = """SELECT TIMESTAMPDIFF(SECOND,date,CURRENT_TIMESTAMP) as diff, message_id
             FROM `replies`
             WHERE `tg_chat_id` = %s
             ORDER BY `id` DESC LIMIT 1"""
    params = (tg_chat_id,)
    for result in cursor.execute(sql, params, multi=True):
        records = cursor.fetchall()
        for row in records:
            res['seconds'] = row[0]
            last_reply_tg_id = row[1]
            print(last_reply_tg_id)
            #messages count after last reply
            sql2 = "SELECT `tg_message_id` FROM `messages` WHERE `tg_chat_id` = %s ORDER BY `id` DESC LIMIT 1"
            params2 = (tg_chat_id,)
            for result2 in cursor.execute(sql2, params2, multi=True):
                records2 = cursor.fetchall()
                for row2 in records2:
                    print(row2[0])
                    res['messages'] = row2[0] - last_reply_tg_id
            sql = "SELECT COUNT(*) FROM `messages` WHERE `tg_chat_id` = %s"
            for result in cursor.execute(sql, (tg_chat_id,), multi=True):
                records = cursor.fetchall()
                for row in records:
                    if row[0] < config['first_message_wait']:
                        pass
    return res

# Return seconds till last interaction
def last_interaction(tg_chat_id, tg_from_id = 0):
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
            sql2 = "SELECT `tg_message_id` FROM `messages` WHERE `tg_chat_id` = %s ORDER BY `id` DESC LIMIT 1"
            params2 = (tg_chat_id,)
            for result2 in cursor.execute(sql2, params2, multi=True):
                records2 = cursor.fetchall()
                for row2 in records2:
                    res['messages'] = row2[0] - last_reply_tg_id
    print(res)
    return res


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


if __name__ == '__main__':
    main()
