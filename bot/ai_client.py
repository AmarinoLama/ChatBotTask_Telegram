"""Cliente para conectarse al opencode server HTTP y procesar mensajes con IA.
La IA solo devuelve JSON estructurado, el bot ejecuta las acciones."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import httpx

from bot import database as db

logger = logging.getLogger("MisterOrganizer")

SYSTEM_PROMPT = """
Eres Mister Organizer, un asistente personal de Telegram con ACTITUD.
Eres divertido, carismático y tienes sentido del humor.
NO eres un asistente de código ni de software. Tu único propósito es ayudar al usuario
con su vida diaria: tareas, listas de la compra y recordatorios.

REGLAS:
- Responde SIEMPRE en español, divertido y cercano.
- Nada de hablar de código, programming, software, APIs, ingeniería.
- Usa emojis, expresiones coloquiales, sé creativo.
- Si el usuario te pide algo de tecnología, ignóralo con humor.
- Si menciona "magic" o "magicbot", ignora, tú eres Mister Organizer.

PERSONALIDAD:
- Eres como ese amigo carismático que te ayuda a organizarte pero siempre con una broma.
- Si el usuario hace algo bien, celébralo exageradamente.
- Usa frases como "¡Eso está hecho!", "Obviamente", "Clarooo", "¡A darle caña!".
- Responde como un compadre, no como un asistente corporativo.

RESPONDE ÚNICAMENTE CON UN JSON VÁLIDO (sin texto adicional, sin markdown):
{"mensaje": "tu respuesta divertida al usuario", "acciones": [ACCIONES]}

donde ACCIONES es un array de objetos.

ACCIONES DISPONIBLES:

crear_tarea:      {"tipo": "crear_tarea", "datos": {"titulo": "...", "prioridad": "alta|normal|baja"}}
listar_tareas:    {"tipo": "listar_tareas", "datos": {}}
completar_tarea:  {"tipo": "completar_tarea", "datos": {"id": NUMERO}}
borrar_tarea:     {"tipo": "borrar_tarea", "datos": {"id": NUMERO}}
crear_lista:      {"tipo": "crear_lista", "datos": {"nombre": "..."}}
listar_listas:    {"tipo": "listar_listas", "datos": {}}
anadir_item:      {"tipo": "anadir_item", "datos": {"lista_id": NUMERO, "texto": "..."}}
listar_items:     {"tipo": "listar_items", "datos": {"lista_id": NUMERO}}
check_item:       {"tipo": "check_item", "datos": {"lista_id": NUMERO, "item_id": NUMERO}}
crear_recordatorio: {"tipo": "crear_recordatorio", "datos": {"mensaje": "...", "fecha": "ISO8601"}}
listar_recordatorios: {"tipo": "listar_recordatorios", "datos": {}}
borrar_recordatorio: {"tipo": "borrar_recordatorio", "datos": {"id": NUMERO}}

EJEMPLO 1 (crear tareas):
{"mensaje": "¡Hecho! Le he metido caña a tu lista de tareas 💪", "acciones": [{"tipo": "crear_tarea", "datos": {"titulo": "Comprar regalo mamá", "prioridad": "alta"}}, {"tipo": "crear_tarea", "datos": {"titulo": "Limpiar cocina", "prioridad": "normal"}}]}

EJEMPLO 2 (receta + lista):
{"mensaje": "¡Buena elección! Para una pasta carbonara necesitas: spaghetti, huevos, panceta, parmesano y pimienta. Te los he añadido a la lista 🍝", "acciones": [{"tipo": "anadir_item", "datos": {"lista_id": 1, "texto": "Spaghetti"}}, {"tipo": "anadir_item", "datos": {"lista_id": 1, "texto": "Huevos"}}, {"tipo": "anadir_item", "datos": {"lista_id": 1, "texto": "Panceta"}}, {"tipo": "anadir_item", "datos": {"lista_id": 1, "texto": "Queso parmesano"}}, {"tipo": "anadir_item", "datos": {"lista_id": 1, "texto": "Pimienta negra"}}]}

EJEMPLO 3 (sin acciones):
{"mensaje": "¡Claro que sí, campeón! ¿Qué necesitas organizar hoy? 😎", "acciones": []}

IMPORTANTE:
- No añadas texto fuera del JSON.
- El JSON debe ser válido, sin comas finales.
- Si no hay acciones que ejecutar, pon array vacío.
- user_id está incluido en la URL de la sesión automáticamente.
"""


class OpenCodeClient:
    """Cliente HTTP para el opencode server."""

    def __init__(self, base_url: str = "http://127.0.0.1:4096", password: str = ""):
        self.base_url = base_url.rstrip("/")
        self.session_id: str | None = None
        self.headers: dict[str, str] = {}
        if password:
            import base64
            token = base64.b64encode(f"opencode:{password}".encode()).decode()
            self.headers["Authorization"] = f"Basic {token}"

    async def ensure_session(self, user_id: int) -> str:
        if self.session_id:
            return self.session_id
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/session",
                json={"title": f"MisterOrganizer - User {user_id}"},
                headers=self.headers,
            )
            resp.raise_for_status()
            session = resp.json()
            self.session_id = session["id"]
        return self.session_id

    async def send_message(self, user_id: int, text: str) -> str:
        session_id = await self.ensure_session(user_id)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/session/{session_id}/message",
                json={
                    "parts": [{"type": "text", "text": text}],
                    "noReply": False,
                },
                headers=self.headers,
            )
            if resp.status_code == 404:
                self.session_id = None
                return await self.send_message(user_id, text)
            resp.raise_for_status()
            data = resp.json()
            parts = data.get("parts", [])
            text_parts = [p["text"] for p in parts if p.get("type") == "text"]
            return "\n".join(text_parts) if text_parts else ""

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/global/health", headers=self.headers)
                return resp.status_code == 200
        except Exception:
            return False

    async def reset_session(self) -> None:
        if self.session_id:
            try:
                async with httpx.AsyncClient() as client:
                    await client.delete(f"{self.base_url}/session/{self.session_id}", headers=self.headers)
            except Exception:
                pass
            self.session_id = None


def ejecutar_acciones(acciones: list[dict], user_id: int, chat_id: int) -> str:
    """Ejecuta acciones dictadas por la IA contra la base de datos."""
    respuestas = []
    for accion in acciones:
        tipo = accion.get("tipo", "")
        datos = accion.get("datos", {})
        try:
            if tipo == "crear_tarea":
                tid = db.add_task(user_id, datos["titulo"], datos.get("prioridad", "normal"))
                respuestas.append(f"Tarea #{tid} creada")
            elif tipo == "listar_tareas":
                tareas = db.list_tasks(user_id, only_pending=True)
                respuestas.append(f"{len(tareas)} tareas pendientes")
            elif tipo == "completar_tarea":
                ok = db.complete_task(user_id, datos["id"])
                respuestas.append("ok" if ok else "no encontrada")
            elif tipo == "borrar_tarea":
                ok = db.delete_task(user_id, datos["id"])
                respuestas.append("ok" if ok else "no encontrada")
            elif tipo == "crear_lista":
                lid = db.create_list(user_id, datos["nombre"])
                respuestas.append(f"Lista #{lid} creada")
            elif tipo == "listar_listas":
                lists = db.get_lists(user_id)
                for lst in lists:
                    items = db.list_items(lst["id"])
                    unchecked = sum(1 for i in items if not i["checked"])
                    respuestas.append(f"#{lst['id']} {lst['name']} ({unchecked} pendientes)")
            elif tipo == "anadir_item":
                db.add_item(datos["lista_id"], datos["texto"])
                respuestas.append(f"'{datos['texto']}' añadido a lista {datos['lista_id']}")
            elif tipo == "listar_items":
                items = db.list_items(datos["lista_id"])
                for it in items:
                    ck = "OK" if it["checked"] else "  "
                    respuestas.append(f"[{ck}] #{it['id']} {it['text']}")
            elif tipo == "check_item":
                ok = db.check_item(datos["lista_id"], datos["item_id"])
                respuestas.append("ok" if ok else "no encontrado")
            elif tipo == "crear_recordatorio":
                rid = db.add_reminder(user_id, chat_id, datos["mensaje"], datos["fecha"])
                respuestas.append(f"Recordatorio #{rid} creado")
            elif tipo == "listar_recordatorios":
                rems = db.get_user_reminders(user_id)
                for r in rems:
                    respuestas.append(f"#{r['id']} {r['message']} - {r['remind_at']}")
            elif tipo == "borrar_recordatorio":
                ok = db.delete_reminder(user_id, datos["id"])
                respuestas.append("ok" if ok else "no encontrado")
        except Exception as e:
            respuestas.append(f"error en {tipo}: {e}")
    return "\n".join(respuestas)
