from telegram import Update
from telegram.ext import ContextTypes
import logging
import traceback
import json
import html
from config import ADMIN_IDS

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logging.error(msg="Exception while handling an update:", exc_info=context.error)

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = html.escape("".join(tb_list))

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"🚨 <b>CRITICAL ERROR</b>\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}</pre>\n\n"
        f"<pre>{tb_string}</pre>"
    )

    # Notify Admin
    for admin_id in ADMIN_IDS:
        try:
            if len(message) > 4096:
                for x in range(0, len(message), 4096):
                    await context.bot.send_message(chat_id=admin_id, text=message[x:x+4096], parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=admin_id, text=message, parse_mode="HTML")
        except:
            pass
