from functools import wraps
from telegram import User, Chat, ChatMember
from telegram.error import BadRequest, Unauthorized

from kaga import (
    DEL_CMDS,
    DEV_USERS,
    SUDO_USERS,
    WHITELIST_USERS,
    dispatcher,
)
from cachetools import TTLCache
from threading import RLock

# refresh cache 10m
ADMIN_CACHE = TTLCache(maxsize=512, ttl=60 * 10)
THREAD_LOCK = RLock()


def can_delete(chat: Chat, bot_id: int) -> bool:
    return chat.get_member(bot_id).can_delete_messages


def is_user_ban_protected(
    chat: Chat, user_id: int, member: ChatMember = None
) -> bool:
    if (
        chat.type == "private"
        or user_id in DEV_USERS
        or user_id in SUDO_USERS
        or user_id in WHITELIST_USERS
        or chat.all_members_are_administrators
        or user_id in (777000, 1087968824)
    ):
        return True

    if not member:
        member = chat.get_member(user_id)
    return member.status in ("administrator", "creator")


def is_user_admin(chat: Chat, user_id: int, member: ChatMember = None) -> bool:
    if (
        chat.type == "private"
        or user_id in DEV_USERS
        or user_id in SUDO_USERS
        or user_id in (777000, 1087968824)
        or chat.all_members_are_administrators
    ):
        return True

    if not member:
        with THREAD_LOCK:
            # try to fetch from cache first.
            try:
                return user_id in ADMIN_CACHE[chat.id]
            except KeyError:
                # keyerror happend means cache is deleted,
                # so query bot api again and return user status
                # while saving it in cache for future useage...
                try:
                    chat_admins = dispatcher.bot.getChatAdministrators(chat.id)
                    admin_list = [x.user.id for x in chat_admins]
                    ADMIN_CACHE[chat.id] = admin_list

                    if user_id in admin_list:
                        return True
                except Unauthorized:
                    return False


def is_bot_admin(
    chat: Chat, bot_id: int, bot_member: ChatMember = None
) -> bool:
    if chat.type == "private" or chat.all_members_are_administrators:
        return True

    if not bot_member:
        bot_member = chat.get_member(bot_id)
    return bot_member.status in ("administrator", "creator")


def is_user_in_chat(chat: Chat, user_id: int) -> bool:
    member = chat.get_member(user_id)
    return member.status not in ("left", "kicked")


def bot_can_delete(func):
    @wraps(func)
    def delete_rights(update, context, *args, **kwargs):
        if can_delete(update.effective_chat, context.bot.id):
            return func(update, context, *args, **kwargs)
        else:
            update.effective_message.reply_text(
                "Saya tidak dapat menghapus pesan di sini! "
                "Pastikan saya admin dan dapat menghapus pesan pengguna lain."
            )

    return delete_rights


def can_pin(func):
    @wraps(func)
    def pin_rights(update, context, *args, **kwargs):
        if update.effective_chat.get_member(context.bot.id).can_pin_messages:
            return func(update, context, *args, **kwargs)
        else:
            update.effective_message.reply_text(
                "Saya tidak dapat memasang pin pada pesan di sini! "
                "Pastikan saya admin dan dapat memasang pin pada pesan."
            )

    return pin_rights


def can_promote(func):
    @wraps(func)
    def promote_rights(update, context, *args, **kwargs):
        if update.effective_chat.get_member(
            context.bot.id
        ).can_promote_members:
            return func(update, context, *args, **kwargs)
        else:
            update.effective_message.reply_text(
                "Saya tidak dapat mempromosikan/menurunkan orang di sini! "
                "Pastikan saya adalah admin dan dapat menunjuk admin baru."
            )

    return promote_rights


def can_restrict(func):
    @wraps(func)
    def promote_rights(update, context, *args, **kwargs):
        if update.effective_chat.get_member(
            context.bot.id
        ).can_restrict_members:
            return func(update, context, *args, **kwargs)
        else:
            update.effective_message.reply_text(
                "Saya tidak dapat membatasi orang di sini! "
                "Pastikan saya adalah admin dan dapat menunjuk admin baru."
            )

    return promote_rights


def bot_admin(func):
    @wraps(func)
    def is_admin(update, context, *args, **kwargs):
        if is_bot_admin(update.effective_chat, context.bot.id):
            return func(update, context, *args, **kwargs)
        else:
            update.effective_message.reply_text("Saya bukan admin!")

    return is_admin


def user_admin(func):
    @wraps(func)
    def is_admin(update, context, *args, **kwargs):
        user = update.effective_user  # type: Optional[User]
        if user and is_user_admin(update.effective_chat, user.id):
            return func(update, context, *args, **kwargs)

        elif not user:
            pass

        elif DEL_CMDS and " " not in update.effective_message.text:
            try:
                update.effective_message.delete()
            except BadRequest:
                pass

        else:
            update.effective_message.reply_text(
                "Anda kehilangan hak admin untuk menggunakan perintah ini!"
            )

    return is_admin


def user_admin_no_reply(func):
    @wraps(func)
    def is_admin(update, context, *args, **kwargs):
        user = update.effective_user  # type: Optional[User]
        if user and is_user_admin(update.effective_chat, user.id):
            return func(update, context, *args, **kwargs)

        elif not user:
            pass

        elif DEL_CMDS and " " not in update.effective_message.text:
            update.effective_message.delete()

    return is_admin


def user_not_admin(func):
    @wraps(func)
    def is_not_admin(update, context, *args, **kwargs):
        user = update.effective_user  # type: Optional[User]
        if user and not is_user_admin(update.effective_chat, user.id):
            return func(update, context, *args, **kwargs)

    return is_not_admin

