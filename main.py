import os
from threading import Thread
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

keep_alive()

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
import database as db

BOT_TOKEN = "8746915562:AAGIx2ptGKmq0PzPNwVh74LYyCTwVHN1gh4"
OWNER_ID = 1772555495

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ADD_BTN_TITLE, ADD_BTN_TYPE, EDIT_BTN_TITLE, ADD_CONTENT, ADD_ADMIN_ID, REMOVE_ADMIN_ID = range(6)

def build_menu_keyboard(parent_id: int = None, is_admin_mode: bool = False) -> InlineKeyboardMarkup:
    buttons = db.get_child_buttons(parent_id)
    keyboard = []
    
    for btn in buttons:
        icon = "📁 " if btn['type'] == 'menu' else "📄 "
        prefix = "adm_" if is_admin_mode else "nav_"
        keyboard.append([InlineKeyboardButton(f"{icon}{btn['title']}", callback_data=f"{prefix}{btn['id']}")])
    
    nav_row = []
    if parent_id is not None:
        curr_btn = db.get_button(parent_id)
        parent_parent_id = curr_btn['parent_id'] if curr_btn else None
        
        back_target = f"{'adm' if is_admin_mode else 'nav'}_{parent_parent_id}" if parent_parent_id else ("adm_main" if is_admin_mode else "nav_main")
        nav_row.append(InlineKeyboardButton("🔙 رجوع", callback_data=back_target))
        
        home_target = "adm_main" if is_admin_mode else "nav_main"
        nav_row.append(InlineKeyboardButton("🏠 الرئيسية", callback_data=home_target))
    
    if nav_row:
        keyboard.append(nav_row)
        
    if is_admin_mode:
        admin_tools = [
            InlineKeyboardButton("➕ إضافة زر", callback_data=f"btn_add_{parent_id if parent_id else 'root'}"),
        ]
        if parent_id is not None:
            admin_tools.extend([
                InlineKeyboardButton("✏️ تعديل اسم الزر", callback_data=f"btn_edit_{parent_id}"),
                InlineKeyboardButton("❌ حذف الزر", callback_data=f"btn_del_{parent_id}")
            ])
            curr_btn = db.get_button(parent_id)
            if curr_btn and curr_btn['type'] == 'content':
                keyboard.append([
                    InlineKeyboardButton("📥 إضافة محتوى", callback_data=f"cnt_add_{parent_id}"),
                    InlineKeyboardButton("🗑️ مسح المحتوى", callback_data=f"cnt_clear_{parent_id}")
                ])
        keyboard.append(admin_tools)
        
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = build_menu_keyboard(parent_id=None, is_admin_mode=False)
    await update.message.reply_text("أهلاً بك! اختر من القوائم التالية:", reply_markup=reply_markup)

async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "nav_main":
        reply_markup = build_menu_keyboard(parent_id=None, is_admin_mode=False)
        await query.edit_message_text("القائمة الرئيسية:", reply_markup=reply_markup)
        return

    button_id = int(data.split("_")[1])
    btn = db.get_button(button_id)
    
    if not btn:
        await query.edit_message_text("عذراً، هذا الزر لم يعد موجوداً.")
        return

    if btn['type'] == 'menu':
        reply_markup = build_menu_keyboard(parent_id=button_id, is_admin_mode=False)
        await query.edit_message_text(f"القائمة: {btn['title']}", reply_markup=reply_markup)
    
    elif btn['type'] == 'content':
        contents = db.get_button_contents(button_id)
        if not contents:
            await query.message.reply_text("لا يوجد محتوى مخزن داخل هذا الزر حالياً.")
            return
        
        await query.message.reply_text(f"⏳ جاري إرسال المحتوى الخاص بـ ({btn['title']})...")
        for item in contents:
            try:
                await context.bot.copy_message(
                    chat_id=query.message.chat_id,
                    from_chat_id=item['from_chat_id'],
                    message_id=item['message_id']
                )
            except Exception as e:
                logging.error(f"Error copying message {item['message_id']}: {e}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.is_admin(user_id):
        await update.message.reply_text("عذراً، لا تمتلك صلاحيات الأدمن.")
        return

    reply_markup = build_menu_keyboard(parent_id=None, is_admin_mode=True)
    text = "🛠️ **لوحة التحكم والتعديل**\nيمكنك التنقل وبناء الأزرار والمحتوى:"
    if db.is_owner(user_id):
        text += "\n\n**أوامر المالك:**\n/addadmin - إضافة مشرف\n/deladmin - إزالة مشرف"
        
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_admin_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "adm_main":
        reply_markup = build_menu_keyboard(parent_id=None, is_admin_mode=True)
        await query.edit_message_text("القائمة الرئيسية (وضع التحكم):", reply_markup=reply_markup)
        return

    button_id = int(data.split("_")[1])
    btn = db.get_button(button_id)
    
    if not btn:
        await query.edit_message_text("هذا الزر غير موجود.")
        return

    reply_markup = build_menu_keyboard(parent_id=button_id, is_admin_mode=True)
    cnt_count = len(db.get_button_contents(button_id)) if btn['type'] == 'content' else 0
    type_str = "قائمة" if btn['type'] == 'menu' else f"محتوى ({cnt_count} عنصر)"
    
    await query.edit_message_text(
        f"⚙️ **تعديل الزر:** {btn['title']}\n**النوع:** {type_str}",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def start_add_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    raw_parent = query.data.split("_")[2]
    context.user_data['parent_id'] = None if raw_parent == 'root' else int(raw_parent)
    await query.message.reply_text("أرسل اسم الزر الجديد:")
    return ADD_BTN_TITLE

async def get_btn_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['btn_title'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("📁 زر قائمة (Sub-menu)", callback_data="type_menu")],
        [InlineKeyboardButton("📄 زر محتوى (Content)", callback_data="type_content")]
    ]
    await update.message.reply_text("اختر نوع الزر:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_BTN_TYPE

async def get_btn_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    btn_type = "menu" if query.data == "type_menu" else "content"
    title = context.user_data['btn_title']
    parent_id = context.user_data['parent_id']
    
    db.add_button(title=title, button_type=btn_type, parent_id=parent_id)
    await query.edit_message_text(f"✅ تم إنشاء الزر ({title}) بنجاح.")
    return ConversationHandler.END

async def start_edit_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['edit_btn_id'] = int(query.data.split("_")[2])
    await query.message.reply_text("أرسل الاسم الجديد للزر:")
    return EDIT_BTN_TITLE

async def save_edited_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn_id = context.user_data['edit_btn_id']
    new_title = update.message.text
    db.update_button_title(btn_id, new_title)
    await update.message.reply_text(f"✅ تم تغيير اسم الزر إلى: {new_title}")
    return ConversationHandler.END

async def delete_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    btn_id = int(query.data.split("_")[2])
    db.delete_button(btn_id)
    await query.edit_message_text("❌ تم حذف الزر وما بداخله.")

async def start_add_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['content_btn_id'] = int(query.data.split("_")[2])
    await query.message.reply_text(
        "قم بإرسال أو توجيه (Forward) الكويزات، الأسئلة، الصور أو الملفات إلى هنا.\n"
        "عند الانتهاء، أرسل أمر **/done** لتأكيد الحفظ."
    )
    return ADD_CONTENT

async def collect_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn_id = context.user_data['content_btn_id']
    msg = update.message
    db.add_content(button_id=btn_id, from_chat_id=msg.chat_id, message_id=msg.message_id)
    await msg.reply_text("✅ تم استلام العنصر. أرسل المزيد أو أرسل /done للإنهاء.")
    return ADD_CONTENT

async def finish_add_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎉 تم حفظ جميع المحتويات المرفوقة للزر بنجاح.")
    return ConversationHandler.END

async def clear_content_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    btn_id = int(query.data.split("_")[2])
    db.clear_button_contents(btn_id)
    await query.edit_message_text("🗑️ تم مسح محتويات هذا الزر.")

async def start_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_owner(update.effective_user.id): return ConversationHandler.END
    await update.message.reply_text("أرسل ID المشرف الجديد:")
    return ADD_ADMIN_ID

async def save_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        admin_id = int(update.message.text.strip())
        db.add_admin(admin_id)
        await update.message.reply_text(f"✅ تم إضافة المشرف {admin_id}.")
    except ValueError:
        await update.message.reply_text("ID غير صحيح.")
    return ConversationHandler.END

async def start_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_owner(update.effective_user.id): return ConversationHandler.END
    await update.message.reply_text("أرسل ID المشرف المراد إزالته:")
    return REMOVE_ADMIN_ID

async def remove_admin_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        admin_id = int(update.message.text.strip())
        db.remove_admin(admin_id)
        await update.message.reply_text(f"✅ تم إزالة المشرف {admin_id}.")
    except ValueError:
        await update.message.reply_text("ID غير صحيح.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

def main():
    db.init_db(OWNER_ID)
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    add_button_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_button, pattern=r"^btn_add_")],
        states={
            ADD_BTN_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_btn_title)],
            ADD_BTN_TYPE: [CallbackQueryHandler(get_btn_type, pattern=r"^type_")]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    edit_button_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_button, pattern=r"^btn_edit_")],
        states={EDIT_BTN_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_edited_title)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    add_content_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_content, pattern=r"^cnt_add_")],
        states={
            ADD_CONTENT: [
                CommandHandler("done", finish_add_content),
                MessageHandler(filters.ALL & ~filters.COMMAND, collect_content)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    add_admin_conv = ConversationHandler(
        entry_points=[CommandHandler("addadmin", start_add_admin)],
        states={ADD_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_admin)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    remove_admin_conv = ConversationHandler(
        entry_points=[CommandHandler("deladmin", start_remove_admin)],
        states={REMOVE_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    
    app.add_handler(add_button_conv)
    app.add_handler(edit_button_conv)
    app.add_handler(add_content_conv)
    app.add_handler(add_admin_conv)
    app.add_handler(remove_admin_conv)
    
    app.add_handler(CallbackQueryHandler(handle_navigation, pattern=r"^nav_"))
    app.add_handler(CallbackQueryHandler(handle_admin_navigation, pattern=r"^adm_"))
    app.add_handler(CallbackQueryHandler(delete_button_handler, pattern=r"^btn_del_"))
    app.add_handler(CallbackQueryHandler(clear_content_handler, pattern=r"^cnt_clear_"))

    print("🚀 البوت يعمل الآن بنجاح...")
    app.run_polling()

if __name__ == "__main__":
    main()
  
