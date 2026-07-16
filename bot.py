"""Bot de Telegram — Mini asistente personal con IA (opencode server)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Cargar .env
_ENV = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENCODE_URL = os.getenv("OPENCODE_URL", "http://127.0.0.1:4096")
OPENCODE_PASSWORD = os.getenv("OPENCODE_SERVER_PASSWORD", "")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("MisterOrganizer")


async def _post_init(app: Application) -> None:
    """Inicializa el cliente IA después de que la app arranque."""
    from bot.ai_client import OpenCodeClient
    client = OpenCodeClient(base_url=OPENCODE_URL, password=OPENCODE_PASSWORD)
    healthy = await client.health()
    if healthy:
        logger.info("✅ opencode server conectado en %s", OPENCODE_URL)
    else:
        logger.warning("⚠️  opencode server NO accesible en %s", OPENCODE_URL)
        logger.warning("   El modo IA no estará disponible hasta que ejecutes: opencode serve")
    app.bot_data["ai_client"] = client


def main() -> None:
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN no encontrado en .env")
        sys.exit(1)

    from bot.database import init_db
    from bot.handlers import (
        TASK_TITLE,
        TASK_PRIORITY,
        LIST_NAME,
        LIST_ADD_ITEMS,
        REMINDER_TEXT,
        REMINDER_TIME,
        handle_message,
        cmd_start,
        cmd_help,
        cmd_tareas,
        cmd_hecho,
        cmd_borrar,
        cmd_listas,
        cmd_ver_lista,
        cmd_anadir,
        cmd_comprado,
        cmd_limpiar,
        cmd_recordatorios,
        cmd_cancelar_recordatorio,
        tarea_start,
        tarea_title,
        tarea_priority,
        lista_start,
        lista_name,
        lista_add_items,
        recordar_start,
        reminder_text,
        reminder_time,
        cancel,
    )

    init_db()
    logger.info("Base de datos inicializada")

    app = Application.builder().token(BOT_TOKEN).post_init(_post_init).build()

    # ── Handler principal de IA (procesa mensajes sin comando) ──
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
    )

    # ── ConversationHandler: Tareas ────────────────────────
    tarea_conv = ConversationHandler(
        entry_points=[CommandHandler("tarea", tarea_start)],
        states={
            TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, tarea_title)],
            TASK_PRIORITY: [CallbackQueryHandler(tarea_priority, pattern=r"^pri:")],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
    )

    # ── ConversationHandler: Listas ────────────────────────
    lista_conv = ConversationHandler(
        entry_points=[CommandHandler("lista", lista_start)],
        states={
            LIST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, lista_name)],
            LIST_ADD_ITEMS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lista_add_items)
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
    )

    # ── ConversationHandler: Recordatorios ─────────────────
    recordar_conv = ConversationHandler(
        entry_points=[CommandHandler("recordar", recordar_start)],
        states={
            REMINDER_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reminder_text)
            ],
            REMINDER_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reminder_time)
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
    )

    # ── Registrar handlers ─────────────────────────────────
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(tarea_conv)
    app.add_handler(lista_conv)
    app.add_handler(recordar_conv)

    # Tareas directas
    app.add_handler(CommandHandler("tareas", cmd_tareas))
    app.add_handler(CommandHandler("hecho", cmd_hecho))
    app.add_handler(CommandHandler("borrar", cmd_borrar))

    # Listas directas
    app.add_handler(CommandHandler("listas", cmd_listas))
    app.add_handler(CommandHandler("ver", cmd_ver_lista))
    app.add_handler(CommandHandler("anadir", cmd_anadir))
    app.add_handler(CommandHandler("comprado", cmd_comprado))
    app.add_handler(CommandHandler("limpiar", cmd_limpiar))

    # Recordatorios directos
    app.add_handler(CommandHandler("recordatorios", cmd_recordatorios))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar_recordatorio))

    logger.info("Bot iniciado — esperando mensajes...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
