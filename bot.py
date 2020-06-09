#Telegram bot to automatically add reactions to channel's posts
#    Copyright (C) 2020  Michele Viotto
import botogram
import i18n
import yaml

import database as db


i18n.load_path.append('langs')
_ = i18n.t # questa funzione è usata per la traduzione dei testi


config = yaml.safe_load(open('config.yml'))

bot = botogram.create(config["bot_token"])
bot.owner = "@sonomichelequellostrano"
supported_langs = config["supported_langs"]


# set commands language
@bot.before_processing
def set_cmd_lang(chat, message):
    """Set commands language based on user telegram language
    or the language the user has set on the settings
    """
    set_language(message.sender)


# COMMANDS
@bot.command('start')
def start_command(chat, message, args):
    sender = message.sender

    add_user_result = db.add_user(sender.id)
    if add_user_result:
        chat.send(_('msg.start_not_subscribed', name=sender.name), attach=langs_btns())
    else:
        chat.send(_('msg.start_command', name=sender.name), attach=main_menu_btns())


# CALLBACKS
@bot.callback("start_callback")
def start_callback(query, chat, message):
    set_language(query.sender)
    message.edit(_('msg.start_command', name=query.sender.name), attach=main_menu_btns())


@bot.callback("set_lang_callback")
def set_lang_callback(query, data, chat, message):
    db.set_user_setting(query.sender.id, 'lang', data)
    set_language(query.sender)
    start_callback(query, chat, message)


@bot.callback("change_language_callback")
def change_language_callback(query, chat, message):
    set_language(query.sender)
    message.edit(_('msg.change_language'), attach=langs_btns())


@bot.callback("add_channel_callback")
def add_channel_callback(query, chat, message):
    set_language(query.sender)
    btns = botogram.Buttons()

    btns[0].callback(_('msg.cancel_operation_button'), "cancel_operation_callback")
    db.set_user_setting(query.sender.id, 'status', 'adding_channel')
    message.edit(_('msg.add_channel'), attach=btns)


@bot.callback("cancel_operation_callback")
def cancel_add_channel(query, chat, message):
    set_language(query.sender)
    db.set_user_setting(query.sender.id, 'status', '')
    start_callback(query, chat, message)


@bot.callback("show_channels_callback")
def show_channels_callback(query, chat, message):
    set_language(query.sender)
    btns = botogram.Buttons()
    channels = db.get_user_channels(query.sender.id)
    msg_text = 'msg.show_channels' if channels else 'msg.no_channels'
    i = 0

    for channel in channels:
        btns[i].callback(bot.chat(channel).title,
                         "configure_channel_callback",
                         str(channel)
                        )
        i += 1
    btns[i].callback(_('msg.cancel_operation_button'), "cancel_operation_callback")

    message.edit(_(msg_text), attach=btns)


@bot.callback("configure_channel_callback")
def configure_channel_callback(query, data, chat, message):
    set_language(query.sender)
    btns = botogram.Buttons()
    btn_emoji = '✅' if db.get_channel_setting(data, 'reactions') else '❌'
    channel = bot.chat(data)

    btns[0].callback(
        _('msg.toggle_reactions_button', status=btn_emoji),
        "toggle_reactions_callback",
        data
    )
    btns[1].callback(_('msg.cancel_operation_button'), "cancel_operation_callback")

    message.edit(_('msg.configure_channel', title=channel.title), attach=btns)


@bot.callback("toggle_reactions_callback")
def toggle_reactions_callback(query, data, chat, message):
    set_language(query.sender)
    db.set_channel_setting(data, 'reactions', not db.get_channel_setting(data, 'reactions'))
    btns = botogram.Buttons()
    btn_emoji = '✅' if db.get_channel_setting(data, 'reactions') else '❌'

    btns[0].callback(
        _('msg.toggle_reactions_button', status=btn_emoji),
        "toggle_reactions_callback",
        data
    )
    btns[1].callback(_('msg.cancel_operation_button'), "cancel_operation_callback")

    message.edit_attach(btns)


@bot.callback("add_reaction_callback")
def add_reaction_callback(query, data, chat, message):
    db.add_user(query.sender.id)
    post = db.get_post(message.id, chat.id)
    sender = query.sender
    reaction = db.get_reaction(post.post_id, sender.id)
    btns = botogram.Buttons()

    # se viene cliccata la stessa reazione la toglie, altrimenti la cambia
    if reaction:
        if reaction.reaction_type == 'upvote':
            if data == 'upvote':
                db.remove_reaction(post.post_id, sender.id)
            elif data == 'downvote':
                db.set_reaction(post.post_id, sender.id, 'downvote')
        elif reaction.reaction_type == 'downvote':
            if data == 'downvote':
                db.remove_reaction(post.post_id, sender.id)
            elif data == 'upvote':
                db.set_reaction(post.post_id, sender.id, 'upvote')
    # aggiunge una nuova reazione
    else:
        db.add_reaction(post.post_id, sender.id, data)
    
    # aggiorna i numeri nei bottoni
    post_reactions = db.get_reactions_count(post.post_id)
    btns[0].callback(f"👍{post_reactions['upvotes']}", "add_reaction_callback", "upvote")
    btns[0].callback(f"👎{post_reactions['downvotes']}", "add_reaction_callback", "downvote")

    message.edit_attach(btns)


@bot.process_message
def process_message(chat, message):
    # "return True" blocca l'esecuzione di ulteriori funzioni da parte di botogram
    if db.get_user_setting(message.sender.id, 'status') == 'adding_channel':
        if isinstance(message.forward_from, botogram.objects.chats.Chat):
            if message.forward_from.type == 'channel':
                channel = message.forward_from
                user = message.sender
                btns = botogram.Buttons()

                if not db.get_channel(channel.id):
                    # provo a mandare un messaggio nel canale, se lo manda
                    # il bot è admin, altrimenti non lo è e chiede di riprovare
                    try:
                        msg = bot.chat(channel.id).send('p')
                        msg.delete() # cancello le tracce del messaggio inviato
                    except botogram.api.APIError:
                        btns[0].callback(
                            _('msg.cancel_operation_button'),
                            "cancel_operation_callback"
                        )
                        chat.send(_('msg.bot_not_in_channel', title=channel.title), attach=btns)

                        return True

                    #  qui il canale viene aggiunto con successo
                    db.set_user_setting(user.id, 'status', '')
                    db.add_channel(channel.id, user.id)
                    btns[0].callback(
                        _('msg.configure_channel_button'),
                        "configure_channel_callback",
                        str(channel.id)
                    )
                    chat.send(_('msg.channel_added', title=channel.title), attach=btns)

                    return True
                else: # il canale è già registrato e non può essere aggiunto di nuovo
                    db.set_user_setting(user.id, 'status', '')
                    chat.send(_('msg.channel_already_added', title=channel.title))

                    return True

        else: # il messaggio inoltrato è di una chat privata o di un gruppo
            btns = botogram.Buttons()

            btns[0].callback(_('msg.cancel_operation_button'), "cancel_operation_callback")
            chat.send(_('msg.wrong_forward_type'), attach=btns)

            return True
    return False

# add buttons to new channel post
@bot.channel_post
def add_buttons_to_post(chat, message):
    db.add_post(message.id, chat.id)
    if db.get_channel_setting(chat.id, 'reactions'):
        btns = botogram.Buttons()
        btns[0].callback("👍", "add_reaction_callback", "upvote")
        btns[0].callback("👎", "add_reaction_callback", "downvote")

        message.edit_attach(btns)


# UTILS FUNCTIONS
# Uso questa funzione in ogni callback perchè non esiste un @bot.before_processing
# per le callback
def set_language(user):
    """Sets message language when using callback
    """
    if not db.get_user(user.id):
        i18n.set('locale', user.lang)
    else:
        i18n.set('locale', db.get_user_setting(user.id, 'lang'))


def main_menu_btns():
    """Returns main menu buttons"""
    btns = botogram.Buttons()

    btns[0].callback(_('msg.add_channel_button'), "add_channel_callback")
    btns[1].callback(_('msg.show_channels_button'), "show_channels_callback")
    btns[2].callback(_('msg.change_language_callback_button'), "change_language_callback")

    return btns


def langs_btns():
    """Returns supported languages buttons"""
    btns = botogram.Buttons()
    i = 0

    for lang in supported_langs:
        btns[i].callback(supported_langs[lang]['emoji'], "set_lang_callback", lang)
        i += 1

    return btns


if __name__ == "__main__":
    bot.run()
