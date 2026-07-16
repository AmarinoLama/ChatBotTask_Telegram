"""Handlers de comandos y conversación del bot de Telegram."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot import database as db

# ── Estados de conversación ─────────────────────────────────
(
    TASK_TITLE,
    TASK_PRIORITY,
    LIST_NAME,
    LIST_ADD_ITEMS,
    LIST_SELECT,
    REMINDER_TEXT,
    REMINDER_TIME,
) = range(7)


def _parse_datetime(text: str) -> datetime | None:
    """Interpreta expresiones de tiempo en español."""
    text = text.strip().lower()
    now = datetime.now(timezone.utc)

    # "en X minutos/horas/días"
    m = re.match(r"en\s+(\d+)\s+(minuto|minutos|hora|horas|dia|días|day|days)", text)
    if m:
        qty = int(m.group(1))
        unit = m.group(2)
        if "minuto" in unit:
            return now + timedelta(minutes=qty)
        elif "hora" in unit:
            return now + timedelta(hours=qty)
        elif "dia" in unit or "day" in unit:
            return now + timedelta(days=qty)

    # "mañana a las HH:MM" o "manana a las HH:MM"
    m = re.match(r"(?:ma[ñn]ana|tomorrow)\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=h, minute=mi, second=0, microsecond=0)

    # "hoy a las HH:MM"
    m = re.match(r"hoy\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        return now.replace(hour=h, minute=mi, second=0, microsecond=0)

    # "a las HH:MM" (asume hoy si aún falta, sino mañana)
    m = re.match(r"a\s+las?\s+(\d{1,2})(?::(\d{2}))?", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        target = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    # "HH:MM" directo
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        target = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    # "dd/mm HH:MM" o "dd/mm/yyyy HH:MM"
    m = re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s+(\d{1,2}):(\d{2})", text)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else now.year
        if year < 100:
            year += 2000
        h, mi = int(m.group(4)), int(m.group(5))
        try:
            return datetime(year, month, day, h, mi, tzinfo=timezone.utc)
        except ValueError:
            return None

    # "lunes/martes/..." a las HH:MM
    days_map = {
        "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
        "viernes": 4, "sabado": 5, "domingo": 6,
    }
    m = re.match(
        r"(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?",
        text,
    )
    if m:
        raw = unicodedata.normalize("NFKD", m.group(1)).lower().replace("é", "e").replace("á", "a")
        target_day = days_map[raw]
        h, mi = int(m.group(2)), int(m.group(3) or 0)
        days_ahead = (target_day - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        target = now + timedelta(days=days_ahead)
        return target.replace(hour=h, minute=mi, second=0, microsecond=0)

    return None


def _format_datetime(dt: datetime) -> str:
    """Formatea datetime para mostrar al usuario."""
    now = datetime.now(timezone.utc)
    diff = dt - now
    parts = []
    if diff.days > 0:
        parts.append(f"{diff.days}d")
    hours = diff.seconds // 3600
    if hours > 0:
        parts.append(f"{hours}h")
    minutes = (diff.seconds % 3600) // 60
    if minutes > 0:
        parts.append(f"{minutes}m")
    time_str = " ".join(parts) if parts else "ahora"
    return dt.strftime(f"%d/%m/%Y %H:%M (en {time_str})")


# ════════════════════════════════════════════════════════════
#  /start y /help
# ════════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (
        f"¡Hola {user.first_name}! 👋 Soy tu asistente personal.\n\n"
        "Puedo ayudarte con:\n"
        "📋 **Tareas** — crear, listar, completar y borrar\n"
        "🛒 **Listas de la compra** — crear listas, añadir productos, marcar comprados\n"
        "⏰ **Recordatorios** — programar avisos para cualquier momento\n\n"
        "Escribe /help para ver todos los comandos."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 **Comandos disponibles**\n\n"
        "**Tareas**\n"
        "  /tarea — crear tarea nueva\n"
        "  /tareas — ver tareas pendientes\n"
        "  /hecho ID — marcar tarea como completada\n"
        "  /borrar ID — eliminar tarea\n\n"
        "**Listas de la compra**\n"
        "  /lista — crear lista nueva\n"
        "  /listas — ver todas tus listas\n"
        "  /ver ID — ver items de una lista\n"
        "  /anadir ID producto — añadir producto a lista\n"
        "  /comprado ID — marcar item como comprado\n"
        "  /limpiar ID — borrar items comprados\n\n"
        "**Recordatorios**\n"
        "  /recordar — crear recordatorio\n"
        "  /recordatorios — ver recordatorios activos\n"
        "  /cancelar ID — cancelar recordatorio\n\n"
        "**Atajos de tiempo** (para recordatorios):\n"
        "  `en 30 minutos`, `en 2 horas`, `en 1 día`\n"
        "  `hoy a las 18:00`, `mañana a las 9:00`\n"
        "  `a las 14:30`, `viernes a las 10:00`\n"
        "  `25/12 09:00`\n\n"
        "**General**\n"
        "  /cancelar — cancelar operación en curso\n"
        "  /help — esta ayuda"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ════════════════════════════════════════════════════════════
#  TAREAS
# ════════════════════════════════════════════════════════════
async def tarea_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📋 **Nueva tarea**\n\nEscribe el título de la tarea:",
        parse_mode="Markdown",
    )
    return TASK_TITLE


async def tarea_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["task_title"] = update.message.text.strip()

    keyboard = [
        [
            InlineKeyboardButton("🔴 Alta", callback_data="pri:high"),
            InlineKeyboardButton("🟡 Normal", callback_data="pri:normal"),
            InlineKeyboardButton("🟢 Baja", callback_data="pri:low"),
        ]
    ]
    await update.message.reply_text(
        "¿Qué prioridad tiene?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return TASK_PRIORITY


async def tarea_priority(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    priority = query.data.split(":")[1]
    title = context.user_data.pop("task_title")
    user_id = update.effective_user.id
    task_id = db.add_task(user_id, title, priority=priority)

    emoji = {"high": "🔴", "normal": "🟡", "low": "🟢"}.get(priority, "⚪")
    await query.edit_message_text(
        f"✅ Tarea creada\n\n{emoji} **{title}**\nID: #{task_id}",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cmd_tareas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    tasks = db.list_tasks(user_id, only_pending=True)

    if not tasks:
        await update.message.reply_text("📋 No tienes tareas pendientes. ¡Genial!")
        return

    lines = ["📋 **Tus tareas pendientes:**\n"]
    for t in tasks:
        emoji = {"high": "🔴", "normal": "🟡", "low": "🟢"}.get(t["priority"], "⚪")
        due = ""
        if t["due_date"]:
            try:
                dt = datetime.fromisoformat(t["due_date"])
                due = f" ⏰ {_format_datetime(dt)}"
            except ValueError:
                pass
        lines.append(f"{emoji} #{t['id']} — {t['title']}{due}")

    lines.append("\nUsa /hecho ID para completar · /borrar ID para eliminar")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_hecho(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /hecho ID\nEjemplo: /hecho 3")
        return

    user_id = update.effective_user.id
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido. Usa /hecho 3")
        return

    task = db.get_task(user_id, task_id)
    if not task:
        await update.message.reply_text(f"❌ No encontré la tarea #{task_id}")
        return

    if db.complete_task(user_id, task_id):
        await update.message.reply_text(f"✅ Tarea completada: **{task['title']}**", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"La tarea #{task_id} ya estaba completada.")


async def cmd_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /borrar ID\nEjemplo: /borrar 3")
        return

    user_id = update.effective_user.id
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido. Usa /borrar 3")
        return

    task = db.get_task(user_id, task_id)
    if not task:
        await update.message.reply_text(f"❌ No encontré la tarea #{task_id}")
        return

    if db.delete_task(user_id, task_id):
        await update.message.reply_text(f"🗑 Tarea eliminada: **{task['title']}**", parse_mode="Markdown")


# ════════════════════════════════════════════════════════════
#  LISTAS DE LA COMPRA
# ════════════════════════════════════════════════════════════
async def lista_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🛒 **Nueva lista de la compra**\n\n¿Cómo quieres llamarla?\nEjemplo: `Supermercado`, `IKEA`, `Farmacia`",
        parse_mode="Markdown",
    )
    return LIST_NAME


async def lista_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    user_id = update.effective_user.id
    list_id = db.create_list(user_id, name)
    context.user_data["current_list_id"] = list_id

    await update.message.reply_text(
        f"✅ Lista **{name}** creada (ID: #{list_id})\n\n"
        "Escribe los productos que quieres añadir, uno por línea.\n"
        "Cuando termines, escribe /done",
        parse_mode="Markdown",
    )
    return LIST_ADD_ITEMS


async def lista_add_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.lower() in ("/done", "done", "terminar"):
        list_id = context.user_data.get("current_list_id")
        items = db.list_items(list_id) if list_id else []
        await update.message.reply_text(
            f"✅ ¡Lista lista! Tienes {len(items)} productos.",
        )
        return ConversationHandler.END

    list_id = context.user_data.get("current_list_id")
    if not list_id:
        await update.message.reply_text("❌ Error: no se encontró la lista.")
        return ConversationHandler.END

    # Añadir cada línea como un item
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    added = 0
    for line in lines:
        db.add_item(list_id, line)
        added += 1

    await update.message.reply_text(
        f"➕ {added} producto(s) añadido(s). "
        "Escribe más o /done para terminar."
    )
    return LIST_ADD_ITEMS


async def cmd_listas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lists = db.get_lists(user_id)

    if not lists:
        await update.message.reply_text("🛒 No tienes listas. Crea una con /lista")
        return

    lines = ["🛒 **Tus listas:**\n"]
    for lst in lists:
        items = db.list_items(lst["id"])
        unchecked = sum(1 for i in items if not i["checked"])
        total = len(items)
        lines.append(f"📝 #{lst['id']} — **{lst['name']}** ({unchecked}/{total} pendientes)")

    lines.append("\nUsa /ver ID para ver productos · /anadir ID producto para añadir")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_ver_lista(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /ver ID\nEjemplo: /ver 2")
        return

    user_id = update.effective_user.id
    try:
        list_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")
        return

    lst = db.get_list(user_id, list_id)
    if not lst:
        await update.message.reply_text(f"❌ No encontré la lista #{list_id}")
        return

    items = db.list_items(list_id)
    if not items:
        await update.message.reply_text(f"📝 Lista **{lst['name']}** vacía.\nUsa /anadir ID producto para añadir.",
                                        parse_mode="Markdown")
        return

    lines = [f"📝 **{lst['name']}**\n"]
    for item in items:
        check = "✅" if item["checked"] else "⬜"
        lines.append(f"{check} #{item['id']} — {item['text']}")

    pending = sum(1 for i in items if not i["checked"])
    checked = sum(1 for i in items if i["checked"])
    lines.append(f"\n{pending} pendientes · {checked} comprados")
    lines.append("Usa /comprado ID · /limpiar ID (borrar comprados)")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_añadir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /anadir LISTA_ID producto\nEjemplo: /anadir 2 leche"
        )
        return

    user_id = update.effective_user.id
    try:
        list_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID de lista inválido.")
        return

    lst = db.get_list(user_id, list_id)
    if not lst:
        await update.message.reply_text(f"❌ No encontré la lista #{list_id}")
        return

    product = " ".join(context.args[1:])
    db.add_item(list_id, product)
    await update.message.reply_text(f"➕ **{product}** añadido a **{lst['name']}**", parse_mode="Markdown")


async def cmd_comprado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /comprado ITEM_ID\nEjemplo: /comprado 5")
        return

    try:
        item_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")
        return

    # Buscar el item en todas las listas del usuario
    user_id = update.effective_user.id
    lists = db.get_lists(user_id)
    found = False
    for lst in lists:
        if db.check_item(lst["id"], item_id):
            found = True
            items = db.list_items(lst["id"])
            item = next((i for i in items if i["id"] == item_id), None)
            name = item["text"] if item else f"#{item_id}"
            pending = sum(1 for i in items if not i["checked"])
            await update.message.reply_text(
                f"✅ **{name}** marcado como comprado.\n"
                f"Quedan {pending} productos en **{lst['name']}**.",
                parse_mode="Markdown",
            )
            break

    if not found:
        await update.message.reply_text(f"❌ No encontré el item #{item_id} en tus listas.")


async def cmd_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /limpiar LISTA_ID\nBorra los items ya comprados.")
        return

    user_id = update.effective_user.id
    try:
        list_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")
        return

    lst = db.get_list(user_id, list_id)
    if not lst:
        await update.message.reply_text(f"❌ No encontré la lista #{list_id}")
        return

    removed = db.clear_checked_items(list_id)
    if removed:
        await update.message.reply_text(f"🗑 {removed} item(s) comprados eliminados de **{lst['name']}**.", parse_mode="Markdown")
    else:
        await update.message.reply_text("No hay items comprados que borrar.")


# ════════════════════════════════════════════════════════════
#  RECORDATORIOS
# ════════════════════════════════════════════════════════════
async def recordar_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "⏰ **Nuevo recordatorio**\n\n¿Qué quieres que te recuerde?",
        parse_mode="Markdown",
    )
    return REMINDER_TEXT


async def reminder_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["reminder_text"] = update.message.text.strip()
    await update.message.reply_text(
        "¿Cuándo quieres el recordatorio?\n\n"
        "Puedes usar:\n"
        "  `en 30 minutos`\n"
        "  `en 2 horas`\n"
        "  `hoy a las 18:00`\n"
        "  `mañana a las 9:00`\n"
        "  `viernes a las 10:00`\n"
        "  `25/12 09:00`\n",
        parse_mode="Markdown",
    )
    return REMINDER_TIME


async def reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    dt = _parse_datetime(text)

    if dt is None:
        await update.message.reply_text(
            "❌ No pude entender esa fecha/hora.\n"
            "Intenta con `en 1 hora` o `mañana a las 9:00`",
            parse_mode="Markdown",
        )
        return REMINDER_TIME

    message = context.user_data.pop("reminder_text")
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    reminder_id = db.add_reminder(user_id, chat_id, message, dt.isoformat())

    # Programar en APScheduler
    job_queue = context.job_queue
    if job_queue:
        job_queue.run_once(
            _send_reminder,
            when=dt,
            data={"chat_id": chat_id, "message": message, "reminder_id": reminder_id},
            name=f"reminder_{reminder_id}",
        )

    await update.message.reply_text(
        f"✅ **Recordatorio guardado**\n\n"
        f"📝 {message}\n"
        f"⏰ {_format_datetime(dt)}\n"
        f"ID: #{reminder_id}",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def _send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback que envía el recordatorio al usuario."""
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    message = job_data["message"]
    reminder_id = job_data["reminder_id"]

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ **Recordatorio**\n\n{message}",
        parse_mode="Markdown",
    )
    db.disable_reminder(reminder_id)


async def cmd_recordatorios(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    reminders = db.get_user_reminders(user_id)

    if not reminders:
        await update.message.reply_text("⏰ No tienes recordatorios activos.")
        return

    lines = ["⏰ **Tus recordatorios:**\n"]
    for r in reminders:
        try:
            dt = datetime.fromisoformat(r["remind_at"])
            when = _format_datetime(dt)
        except ValueError:
            when = r["remind_at"]
        lines.append(f"🔔 #{r['id']} — {r['message']}\n    ⏰ {when}")

    lines.append("\nUsa /cancelar ID para cancelar uno")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_cancelar_recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /cancelar ID\nEjemplo: /cancelar 5")
        return

    user_id = update.effective_user.id
    try:
        reminder_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")
        return

    if db.delete_reminder(user_id, reminder_id):
        # Eliminar job de APScheduler
        job_queue = context.job_queue
        if job_queue:
            job_queue_jobs = job_queue.get_jobs_by_name(f"reminder_{reminder_id}")
            for job in job_queue_jobs:
                job.schedule_removal()
        await update.message.reply_text(f"✅ Recordatorio #{reminder_id} cancelado.")
    else:
        await update.message.reply_text(f"❌ No encontré el recordatorio #{reminder_id}")


# ════════════════════════════════════════════════════════════
#  Cancelar conversación
# ════════════════════════════════════════════════════════════
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END
