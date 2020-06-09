#Telegram bot to automatically add reactions to channel's posts
#    Copyright (C) 2020  Michele Viotto
from decimal import Decimal
from pony.orm import *
import yaml

db = Database()
config = yaml.safe_load(open('config.yml'))['database_data']

class User(db.Entity):
    user_id = PrimaryKey(int)
    lang = Required(str, default='en')
    status = Optional(str)
    channels = Set('Channel')
    reactions = Set('Reaction')


class Channel(db.Entity):
    channel_id = PrimaryKey(Decimal, 20, 1)
    reactions = Required(bool, default=1)
    comments = Required(bool, default=1)
    user = Required(User)
    posts = Set('Post')


class Post(db.Entity):
    post_id = PrimaryKey(int, auto=True)
    message_id = Required(int)
    channel = Required(Channel)
    reactions = Set('Reaction')


class Reaction(db.Entity):
    reaction_type = Optional(str)
    post = Required(Post)
    user = Required(User)
    PrimaryKey(post, user)


db.bind(provider=config['provider'],
        user=config['user'],
        password=config['password'],
        host=config['host'],
        database=config['database'])
db.generate_mapping(create_tables=True)


# USERS
@db_session
def get_user(user_id):
    try:
        return User[user_id]
    except ObjectNotFound:
        return False


@db_session
def add_user(user_id):
    if not get_user(user_id):
        User(user_id=user_id)
        return True

    return False


@db_session
def remove_user(user_id):
    try:
        User[user_id].delete()
        return True
    except ObjectNotFound:
        return False


@db_session
def get_user_setting(user_id, setting):
    try:
        user = User[user_id].to_dict()
        return user[setting]
    except (ObjectNotFound, KeyError):
        return False


@db_session
def set_user_setting(user_id, setting, value):
    try:
        user = User[user_id].to_dict()
        user[setting] = value
        User[user_id].set(**user)
        return True
    except (ObjectNotFound, TypeError):
        return False


# CHANNELS
@db_session
def get_channel(channel_id):
    try:
        return Channel[channel_id]
    except ObjectNotFound:
        return False


@db_session
def add_channel(channel_id, user_id):
    if not get_channel(channel_id) and get_user(user_id):
        Channel(channel_id=channel_id, user=User[user_id])
        return True

    return False


@db_session
def remove_channel(channel_id):
    try:
        Channel[channel_id].delete()
        return True
    except ObjectNotFound:
        return False


@db_session
def get_channel_setting(channel_id, setting):
    try:
        channel = Channel[channel_id].to_dict()
        return channel[setting]
    except (ObjectNotFound, KeyError):
        return False


@db_session
def set_channel_setting(channel_id, setting, value):
    try:
        channel = Channel[channel_id].to_dict()
        channel[setting] = value
        Channel[channel_id].set(**channel)
        return True
    except (ObjectNotFound, TypeError):
        return False


@db_session
def get_user_channels(user_id):
    """Returns all the channels for user_id"""
    try:
        result = select((channel.channel_id) for channel in Channel if channel.user == User[user_id])[:]
        return result
    except (ObjectNotFound, ExprEvalError):
        return False


# POSTS
@db_session
def add_post(message_id, channel_id):
    if not get_post(message_id, channel_id):
        Post(message_id=message_id, channel=Channel[channel_id])
        return True

    return False


@db_session
def get_post(message_id, channel_id):
    try:
        result = select(
            post for post in Post
            if post.message_id == message_id
            and post.channel == Channel[channel_id]
        )[:]
        return result[0] if result else False
    except (ObjectNotFound, ExprEvalError):
        return False

# REACTIONS
@db_session
def add_reaction(post_id, user_id, reaction_type):
    if not get_reaction(post_id, user_id):
        Reaction(reaction_type=reaction_type, post=Post[post_id], user=User[user_id])
        return True
    
    return False


@db_session
def get_reaction(post_id, user_id):
    try:
        result = select(
            reaction for reaction in Reaction
            if reaction.post == Post[post_id]
            and reaction.user == User[user_id]
        )[:]
        return result[0] if result else False
    except (ObjectNotFound, ExprEvalError):
        return False


@db_session
def remove_reaction(post_id, user_id):
    try:
        reaction = get_reaction(post_id, user_id)
        reaction.delete()
        return True
    except (ObjectNotFound, ExprEvalError):
        return False


@db_session
def set_reaction(post_id, user_id, reaction_type):
    try:
        reaction = get_reaction(post_id, user_id)
        reaction.reaction_type = reaction_type
        return True
    except (ObjectNotFound, TypeError):
        return False


@db_session
def get_reactions_count(post_id):
    try:
        upvotes = select(
            count(upvote) for upvote in Reaction
            if upvote.reaction_type == 'upvote'
            and upvote.post == Post[post_id]
        )[:][0]
        downvotes = select(
            count(downvote) for downvote in Reaction
            if downvote.reaction_type == 'downvote'
            and downvote.post == Post[post_id]
        )[:][0]

        return {'upvotes': upvotes, 'downvotes': downvotes}
    except (ObjectNotFound, ExprEvalError):
        return False
