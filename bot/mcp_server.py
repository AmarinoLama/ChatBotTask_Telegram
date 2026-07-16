"""MCP server que expone las funciones de la base de datos como tools.
Opencode server lo usará como MCP local para que la IA pueda
manejar tareas, listas y recordatorios del bot."""

from __future__ import annotations

import sys
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from bot import database as db

server = Server("telegram-bot-db")


# ── TAREAS ───────────────────────────────────────────────────

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="add_task",
            description="Crear una nueva tarea",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "ID del usuario de Telegram"},
                    "title": {"type": "string", "description": "Título de la tarea"},
                    "priority": {"type": "string", "enum": ["high", "normal", "low"], "description": "Prioridad (alta/normal/baja)"},
                },
                "required": ["user_id", "title"],
            },
        ),
        types.Tool(
            name="list_tasks",
            description="Listar tareas pendientes de un usuario",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "ID del usuario de Telegram"},
                },
                "required": ["user_id"],
            },
        ),
        types.Tool(
            name="complete_task",
            description="Marcar una tarea como completada",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer"},
                    "task_id": {"type": "integer"},
                },
                "required": ["user_id", "task_id"],
            },
        ),
        types.Tool(
            name="delete_task",
            description="Eliminar una tarea",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer"},
                    "task_id": {"type": "integer"},
                },
                "required": ["user_id", "task_id"],
            },
        ),
        # ── LISTAS ─────────────────────────────────────────
        types.Tool(
            name="create_list",
            description="Crear una nueva lista de la compra",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer"},
                    "name": {"type": "string", "description": "Nombre de la lista"},
                },
                "required": ["user_id", "name"],
            },
        ),
        types.Tool(
            name="get_lists",
            description="Obtener todas las listas de un usuario",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer"},
                },
                "required": ["user_id"],
            },
        ),
        types.Tool(
            name="add_item",
            description="Añadir un producto a una lista",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_id": {"type": "integer"},
                    "text": {"type": "string", "description": "Nombre del producto"},
                },
                "required": ["list_id", "text"],
            },
        ),
        types.Tool(
            name="list_items",
            description="Ver productos de una lista",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_id": {"type": "integer"},
                },
                "required": ["list_id"],
            },
        ),
        types.Tool(
            name="check_item",
            description="Marcar un producto como comprado",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_id": {"type": "integer"},
                    "item_id": {"type": "integer"},
                },
                "required": ["list_id", "item_id"],
            },
        ),
        types.Tool(
            name="clear_checked_items",
            description="Eliminar todos los productos comprados de una lista",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_id": {"type": "integer"},
                },
                "required": ["list_id"],
            },
        ),
        # ── RECORDATORIOS ──────────────────────────────────
        types.Tool(
            name="add_reminder",
            description="Crear un recordatorio para un usuario",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer"},
                    "chat_id": {"type": "integer"},
                    "message": {"type": "string", "description": "Mensaje del recordatorio"},
                    "remind_at": {"type": "string", "description": "Fecha ISO 8601 (ej: 2025-12-25T09:00:00+00:00)"},
                },
                "required": ["user_id", "chat_id", "message", "remind_at"],
            },
        ),
        types.Tool(
            name="get_user_reminders",
            description="Ver recordatorios activos de un usuario",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer"},
                },
                "required": ["user_id"],
            },
        ),
        types.Tool(
            name="delete_reminder",
            description="Cancelar/eliminar un recordatorio",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer"},
                    "reminder_id": {"type": "integer"},
                },
                "required": ["user_id", "reminder_id"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent]:
    args = arguments or {}

    try:
        if name == "add_task":
            result = db.add_task(args["user_id"], args["title"], args.get("priority", "normal"))
            return [types.TextContent(type="text", text=f"Tarea creada con ID #{result}")]

        elif name == "list_tasks":
            tasks = db.list_tasks(args["user_id"], only_pending=True)
            if not tasks:
                return [types.TextContent(type="text", text="No hay tareas pendientes.")]
            return [types.TextContent(type="text", text=str(tasks))]

        elif name == "complete_task":
            ok = db.complete_task(args["user_id"], args["task_id"])
            return [types.TextContent(type="text", text="ok" if ok else "no_encontrada")]

        elif name == "delete_task":
            ok = db.delete_task(args["user_id"], args["task_id"])
            return [types.TextContent(type="text", text="ok" if ok else "no_encontrada")]

        elif name == "create_list":
            list_id = db.create_list(args["user_id"], args["name"])
            return [types.TextContent(type="text", text=f"Lista creada con ID #{list_id}")]

        elif name == "get_lists":
            lists = db.get_lists(args["user_id"])
            return [types.TextContent(type="text", text=str(lists))]

        elif name == "add_item":
            item_id = db.add_item(args["list_id"], args["text"])
            return [types.TextContent(type="text", text=f"Producto añadido con ID #{item_id}")]

        elif name == "list_items":
            items = db.list_items(args["list_id"])
            return [types.TextContent(type="text", text=str(items))]

        elif name == "check_item":
            ok = db.check_item(args["list_id"], args["item_id"])
            return [types.TextContent(type="text", text="ok" if ok else "no_encontrado")]

        elif name == "clear_checked_items":
            n = db.clear_checked_items(args["list_id"])
            return [types.TextContent(type="text", text=f"{n} items eliminados")]

        elif name == "add_reminder":
            rid = db.add_reminder(args["user_id"], args["chat_id"], args["message"], args["remind_at"])
            return [types.TextContent(type="text", text=f"Recordatorio creado con ID #{rid}")]

        elif name == "get_user_reminders":
            reminders = db.get_user_reminders(args["user_id"])
            return [types.TextContent(type="text", text=str(reminders))]

        elif name == "delete_reminder":
            ok = db.delete_reminder(args["user_id"], args["reminder_id"])
            return [types.TextContent(type="text", text="ok" if ok else "no_encontrado")]

        else:
            raise ValueError(f"Tool desconocido: {name}")

    except Exception as e:
        return [types.TextContent(type="text", text=f"error: {e}")]


async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="telegram-bot-db",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
