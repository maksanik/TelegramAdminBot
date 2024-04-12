import sqlite3
import configparser
import telebot
from telebot import types

config = configparser.ConfigParser()
config.read("config/сonfig.ini") # put your data in config


bot = telebot.TeleBot(config["Default"]["bot_id"])
ADMIN_CHAT_ID = int(config["Default"]["admin_chat_id"])
SUPER_ADMIN_ID = int(config["Default"]["super_admin_id"])
CHANNEL_ID = int(config["Default"]["channel_id"])
DATABASE = config["Default"]["database_path"]


@bot.message_handler(commands=['start', 'help'])
def start(message):
    """Start message"""
    
    bot.send_message(
        message.chat.id, '''Привет! Чтобы отправить пост в предложку, отправь картинку/видео или картинку/видео с текстом, чтобы она ушла на проверку.''') 

@bot.message_handler(commands=['check_id'])
def check(message):
    """Check id"""
    
    if message.from_user.id != SUPER_ADMIN_ID:
        return

    bot.send_message(message.chat.id, message.chat.id)
    
@bot.message_handler(commands=['delete_all'])
def delete_all(message):
    """Deletes all posts in chat of admins and clears tables"""
    
    if message.from_user.id != SUPER_ADMIN_ID:
        return

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute("SELECT message_id FROM Posts")
    messages_to_delete = [el[0] for el in cur.fetchall()]
    cur.execute("DELETE FROM Posts")
    conn.commit()
    cur.close()
    conn.close()

    if len(messages_to_delete) > 0:
        bot.delete_messages(ADMIN_CHAT_ID, messages_to_delete)
        bot.send_message(message.chat.id, "Выполнено")

@bot.message_handler(commands=['delete'])
def delete(message):
    """Delete current post"""
    
    if message.from_user.id != SUPER_ADMIN_ID or message.chat.id != ADMIN_CHAT_ID:
        return
    
    msg = message.reply_to_message
    
    if msg.content_type not in ["photo", "video"]:
        return
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM Posts WHERE message_id = {msg.id}")
    conn.commit()
    conn.close()
    bot.delete_message(ADMIN_CHAT_ID, msg.id)
    bot.send_message(message.chat.id, "Пост удалён!")

@bot.message_handler(commands=['post'])
def delete(message):
    """Publish current post"""
    
    if message.from_user.id != SUPER_ADMIN_ID or message.chat.id != ADMIN_CHAT_ID:
        return
    
    msg = message.reply_to_message
    
    if msg.content_type not in ["photo", "video"]:
        return
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM Posts WHERE message_id = {msg.id}")
    conn.commit()
    conn.close()
    
    if msg.content_type == "photo":
            bot.send_photo(CHANNEL_ID, msg.photo[0].file_id, caption=msg.caption)
    elif msg.content_type == "video":
            bot.send_video(CHANNEL_ID, msg.video.file_id, caption=msg.caption)
             
    bot.delete_message(msg.chat.id, msg.id)
    bot.send_message(ADMIN_CHAT_ID, "Пост опубликован!")


@bot.message_handler(content_types=["photo", "video"])
def get_post(message):
    """Get posts from users and re-send it to admin chat"""
    
    with sqlite3.connect(DATABASE) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute(f"SELECT message_id FROM Posts WHERE user_id = {message.from_user.id}")
        posts_amount = len(cur.fetchall())
        conn.commit()
        cur.close()
    
    if posts_amount >= 3:
        bot.reply_to(message, "Нельзя отправить много постов за раз! Дождитесь проверки ранее отправленных постов.")
        return

    bot.reply_to(message, "Ваш пост отправлен на проверку!")

    markup = types.InlineKeyboardMarkup()
    likes = types.InlineKeyboardButton("👍:0", callback_data="like")
    dislikes = types.InlineKeyboardButton("👎:0", callback_data="dislike")
    markup.row(likes, dislikes)

    if message.content_type == "photo":
        bot_msg = bot.send_photo(
                ADMIN_CHAT_ID, message.photo[0].file_id,
                caption=message.caption,
                reply_markup=markup)

    elif message.content_type == "video":
        bot_msg = bot.send_video(
                ADMIN_CHAT_ID, message.video.file_id,
                caption=message.caption,
                reply_markup=markup)

    with sqlite3.connect(DATABASE) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute(f'''INSERT INTO Posts (message_id, user_id, post_date)
                    VALUES ({bot_msg.message_id},{message.from_user.id},{bot_msg.date})''')
        conn.commit()
        cur.close()


@bot.callback_query_handler(func=lambda x: True)
def callback_reactions(callback):
    """Handler for likes and dislikes"""

    msg = callback.message

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute(f'''SELECT * FROM Reactions 
                WHERE message_id = {callback.message.message_id} 
                AND admin_id = {callback.from_user.id}''')
    prev = cur.fetchall()
    #TODO: Переделать в функции в отдельном модуле
    if len(prev) == 0:
        cur.execute(f'''INSERT INTO Reactions (message_id, admin_id, reaction) 
                    VALUES ({callback.message.message_id},
                    {callback.from_user.id},
                    "{callback.data}")''')
    else:
        cur.execute(f'''UPDATE Reactions SET reaction = "{callback.data}"
                    WHERE message_id = {callback.message.message_id}
                    AND admin_id = {callback.from_user.id}''')

    cur.execute(f'''SELECT * FROM Reactions 
                WHERE message_id = {callback.message.message_id}
                AND reaction = "like"''')
    likes = len(cur.fetchall())

    cur.execute(f'''SELECT * FROM Reactions
                WHERE message_id = {callback.message.message_id}
                AND reaction = "dislike"''')
    dislikes = len(cur.fetchall())

    cur.close()
    conn.commit()
    conn.close()


    msg.reply_markup.keyboard[0][0].text = "👍:" + str(likes)
    msg.reply_markup.keyboard[0][1].text = "👎:" + str(dislikes)

    try:
        bot.edit_message_reply_markup(ADMIN_CHAT_ID, msg.message_id,
                                      reply_markup = msg.reply_markup)
    except telebot.apihelper.ApiTelegramException:
        pass # TODO: Подключить logging
    
    should_be_deleted = False
    
    if likes > dislikes + 2:
        if msg.content_type == "photo":
            bot.send_photo(CHANNEL_ID, msg.photo[0].file_id, caption=msg.caption)
        elif msg.content_type == "video":
            bot.send_video(CHANNEL_ID, msg.video.file_id, caption=msg.caption)
            
        bot.delete_message(msg.chat.id, msg.id)
        should_be_deleted = True
        bot.send_message(ADMIN_CHAT_ID, "Пост опубликован!")
        
    elif dislikes > likes + 2:
        bot.delete_message(msg.chat.id, msg.id)
        should_be_deleted = True
        bot.send_message(ADMIN_CHAT_ID, "Пост удалён!")
        
    if should_be_deleted:
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute(f"DELETE FROM Posts WHERE message_id = {msg.id}")
        conn.commit()
        cur.close()
        conn.close()

    bot.answer_callback_query(callback.id)
  
bot.polling(none_stop=True)
