"""Handlers de comandos y conversación del bot de Telegram.
Modo IA: procesa mensajes en lenguaje natural mediante opencode server."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot import database as db
from bot.ai_client import ejecutar_acciones

logger = logging.getLogger("MisterOrganizer")

# Estados de conversación (legacy, para compatibilidad)
(
    TASK_TITLE,
    TASK_PRIORITY,
    LIST_NAME,
    LIST_ADD_ITEMS,
    LIST_SELECT,
    REMINDER_TEXT,
    REMINDER_TIME,
) = range(7)


# ════════════════════════════════════════════════════════════
#  Handler principal de IA
# ════════════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa mensajes con IA: opencode responde JSON, el bot ejecuta."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    ai_client = context.bot_data.get("ai_client")
    if not ai_client:
        await update.message.reply_text(
            "⚠️ Mister Organizer no está disponible. Asegúrate de que opencode server esté corriendo."
        )
        return

    try:
        raw = await ai_client.send_message(user_id, text)
        if not raw:
            await update.message.reply_text("🤔 No entendí bien, ¿puedes repetirlo?")
            return

        data = json.loads(raw)
        mensaje = data.get("mensaje", "¡Hecho!")
        acciones = data.get("acciones", [])

        if acciones:
            resumen = ejecutar_acciones(acciones, user_id, chat_id)
            logger.info("Acciones ejecutadas: %s", resumen)

        await update.message.reply_text(mensaje)

    except json.JSONDecodeError:
        logger.warning("Respuesta no-JSON de la IA, se muestra cruda")
        await update.message.reply_text(raw[:4096])
    except Exception as e:
        logger.exception("Error en handler de IA")
        await update.message.reply_text(f"❌ Vaya, algo salió mal... {str(e)[:200]}")


# ════════════════════════════════════════════════════════════
#  /start y /help
# ════════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (
        f"¡Hola {user.first_name}! 👋 Soy **Mister Organizer**, tu asistente personal con IA.\n\n"
        "Puedes hablarme en lenguaje natural. Por ejemplo:\n"
        "• \"Crea una tarea para comprar el regalo de mamá\"\n"
        "• \"¿Qué tareas tengo pendientes?\"\n"
        "• \"Añade leche y pan a la lista de la compra\"\n"
        "• \"Recuérdame lo de la reunion en 2 horas\"\n"
        "• \"¿Qué ingredientes necesita una paella? Añádelos a mi lista\"\n"
        "• \"Recomiéndame una rutina de estudio para hoy\"\n\n"
        "Escribe /help si quieres ver los comandos tradicionales."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 **Comandos disponibles**\n\n"
        "**Modo principal (recomendado)**\n"
        "Simplemente escríbeme lo que necesitas en lenguaje natural.\n"
        "Ej: \"Añade leche a la lista\", \"Crea tarea: limpiar cocina\"\n\n"
        "**Comandos tradicionales**\n"
        "  /start — bienvenida\n"
        "  /help — esta ayuda\n"
        "  /tarea — crear tarea (guiado)\n"
        "  /tareas — ver tareas pendientes\n"
        "  /hecho ID — completar tarea\n"
        "  /borrar ID — eliminar tarea\n"
        "  /lista — crear lista (guiado)\n"
        "  /listas — ver listas\n"
        "  /ver ID — ver productos\n"
        "  /anadir ID producto — añadir rápido\n"
        "  /comprado ID — marcar comprado\n"
        "  /limpiar ID — limpiar comprados\n"
        "  /recordar — crear recordatorio (guiado)\n"
        "  /recordatorios — ver recordatorios\n"
        "  /cancelar ID — cancelar recordatorio\n"
        "  /cancelar — cancelar operación"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ════════════════════════════════════════════════════════════
#  TAREAS (legacy / comandos directos)
# ════════════════════════════════════════════════════════════
async def tarea_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📋 **Nueva tarea**\n\nEscribe el título de la tarea:",
        parse_mode="Markdown",
    )
    return TASK_TITLE


async def tarea_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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
                diff = dt - datetime.now(timezone.utc)
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
                due = f" ⏰ {dt.strftime(f'%d/%m/%Y %H:%M (en {time_str})')}"
            except ValueError:
                pass
        lines.append(f"{emoji} #{t['id']} — {t['title']}{due}")
    lines.append("\nUsa /hecho ID · /borrar ID")
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
#  LISTAS DE LA COMPRA (legacy)
# ════════════════════════════════════════════════════════════
async def lista_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🛒 **Nueva lista de la compra**\n\n¿Cómo quieres llamarla?\nEjemplo: `Supermercado`, `IKEA`",
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
        "Escribe los productos, uno por línea.\n"
        "/done para terminar",
        parse_mode="Markdown",
    )
    return LIST_ADD_ITEMS


async def lista_add_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.lower() in ("/done", "done", "terminar"):
        list_id = context.user_data.get("current_list_id")
        items = db.list_items(list_id) if list_id else []
        await update.message.reply_text(f"✅ ¡Lista lista! Tienes {len(items)} productos.")
        return ConversationHandler.END
    list_id = context.user_data.get("current_list_id")
    if not list_id:
        await update.message.reply_text("❌ Error: no se encontró la lista.")
        return ConversationHandler.END
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    added = 0
    for line in lines:
        db.add_item(list_id, line)
        added += 1
    await update.message.reply_text(f"➕ {added} producto(s) añadido(s). Escribe más o /done para terminar.")
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
    lines.append("\nUsa /ver ID · /anadir ID producto")
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
        await update.message.reply_text(f"📝 Lista **{lst['name']}** vacía.", parse_mode="Markdown")
        return
    lines = [f"📝 **{lst['name']}**\n"]
    for item in items:
        check = "✅" if item["checked"] else "⬜"
        lines.append(f"{check} #{item['id']} — {item['text']}")
    pending = sum(1 for i in items if not i["checked"])
    checked = sum(1 for i in items if i["checked"])
    lines.append(f"\n{pending} pendientes · {checked} comprados")
    lines.append("Usa /comprado ID · /limpiar ID")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_anadir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /anadir LISTA_ID producto\nEjemplo: /anadir 2 leche")
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
                f"✅ **{name}** marcado como comprado.\nQuedan {pending} productos en **{lst['name']}**.",
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
#  RECORDATORIOS (legacy)
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
        "¿Cuándo?\nEj: `en 30 minutos`, `hoy a las 18:00`, `mañana a las 9:00`",
        parse_mode="Markdown",
    )
    return REMINDER_TIME


def _parse_datetime(text: str) -> datetime | None:
    """Interpreta expresiones de tiempo en español."""
    text = text.strip().lower()
    now = datetime.now(timezone.utc)
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
    m = re.match(r"(?:ma[ñn]ana|tomorrow)\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        return (now + timedelta(days=1)).replace(hour=h, minute=mi, second=0, microsecond=0)
    m = re.match(r"hoy\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        return now.replace(hour=h, minute=mi, second=0, microsecond=0)
    m = re.match(r"a\s+las?\s+(\d{1,2})(?::(\d{2}))?", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        target = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        target = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target
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
    days_map = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
    m = re.match(r"(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?", text)
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


async def reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    dt = _parse_datetime(text)
    if dt is None:
        await update.message.reply_text(
            "❌ No pude entender esa fecha.\nIntenta con `en 1 hora` o `mañana a las 9:00`",
            parse_mode="Markdown",
        )
        return REMINDER_TIME
    message = context.user_data.pop("reminder_text")
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    reminder_id = db.add_reminder(user_id, chat_id, message, dt.isoformat())
    job_queue = context.job_queue
    if job_queue:
        job_queue.run_once(
            _send_reminder,
            when=dt,
            data={"chat_id": chat_id, "message": message, "reminder_id": reminder_id},
            name=f"reminder_{reminder_id}",
        )
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
    await update.message.reply_text(
        f"✅ **Recordatorio guardado**\n\n📝 {message}\n⏰ {dt.strftime(f'%d/%m/%Y %H:%M (en {time_str})')}\nID: #{reminder_id}",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def _send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data
    await context.bot.send_message(
        chat_id=job_data["chat_id"],
        text=f"⏰ **Recordatorio**\n\n{job_data['message']}",
        parse_mode="Markdown",
    )
    db.disable_reminder(job_data["reminder_id"])


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
            when = dt.strftime(f"%d/%m/%Y %H:%M (en {' '.join(parts) if parts else 'ahora'})")
        except ValueError:
            when = r["remind_at"]
        lines.append(f"🔔 #{r['id']} — {r['message']}\n    ⏰ {when}")
    lines.append("\nUsa /cancelar ID")
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
        job_queue = context.job_queue
        if job_queue:
            for job in job_queue.get_jobs_by_name(f"reminder_{reminder_id}"):
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
