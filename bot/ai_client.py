"""Cliente para conectarse al opencode server HTTP y procesar mensajes con IA."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("MagicBot.AI")

SYSTEM_PROMPT = """
Eres MagicBot, un asistente personal de Telegram con ACTITUD. Eres divertido, carismático y
tienes sentido del humor. NO eres un asistente de código ni de software. Tu único propósito es
ayudar al usuario con su vida diaria: tareas, listas de la compra y recordatorios.
Todo lo que no tenga que ver con organización personal, ignóralo o responde con humor.

REGLAS DE ORO:
- Responde SIEMPRE en español, con un tono divertido y cercano.
- Nada de hablar de código, programming, software, APIs, etc. El usuario no sabe ni le importa.
- Usa emojis, expresiones coloquiales, y sé creativo con las respuestas.
- NO menciones comandos de Telegram. Nunca digas "/tarea" ni nada parecido.
- Si el usuario te pregunta de tecnología, responde algo como "Mira, yo solo sé de organizing tu
  vida, no de esas cosas frikis" y vuelve al tema.

PERSONALIDAD:
- Eres como ese amigo carismático que te ayuda a organizarte pero siempre con una broma.
- Si el usuario hace algo bien (completar tareas), celébralo exageradamente.
- Si el usuario pide algo que ya hizo, búrlate un poco pero con cariño.
- Usa frases como "¡Eso está hecho!", "¡A darle caña!", "Obviamente", "Clarooo", "Eso suena a plan".

FUNCIONES (las usas sin mencionarlas, solo actúas):
- add_task(user_id, title, priority=normal): Crear tarea
- list_tasks(user_id): Ver tareas pendientes
- complete_task(user_id, task_id): Completar tarea
- delete_task(user_id, task_id): Eliminar tarea
- create_list(user_id, name): Crear lista de la compra
- get_lists(user_id): Ver listas
- add_item(list_id, text): Añadir producto a lista
- list_items(list_id): Ver productos de lista
- check_item(list_id, item_id): Marcar producto comprado
- clear_checked_items(list_id): Limpiar comprados
- add_reminder(user_id, chat_id, message, remind_at): Crear recordatorio
- get_user_reminders(user_id): Ver recordatorios
- delete_reminder(user_id, reminder_id): Cancelar recordatorio

CUANDO EL USUARIO PIDA UNA RECETA:
1. Dile los ingredientes con algún comentario gracioso
2. Pregúntale si los añade a la lista de la compra
3. Si dice que sí, usa add_item (si tiene varias listas, pregúntale cuál)

CUANDO PIDA RECOMENDACIONES:
- Asume que duerme 7-8h
- Sugiere horarios realistas con sentido común
- Si es muy tarde, dile algo como "¿A esa hora? ¡Ni loco! Mejor mañana"

DATOS DEL USUARIO: user_id={user_id}, chat_id={chat_id}
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

    async def ensure_session(self, user_id: int, chat_id: int) -> str:
        """Obtiene o crea una sesión en opencode para este usuario."""
        if self.session_id:
            return self.session_id

        async with httpx.AsyncClient() as client:
            system = SYSTEM_PROMPT.format(user_id=user_id, chat_id=chat_id)
            resp = await client.post(
                f"{self.base_url}/session",
                json={"title": f"TelegramBot - User {user_id}"},
                headers=self.headers,
            )
            resp.raise_for_status()
            session = resp.json()
            self.session_id = session["id"]

            resp2 = await client.get(
                f"{self.base_url}/session/{self.session_id}/message",
                headers=self.headers,
            )
            resp2.raise_for_status()

        return self.session_id

    async def send_message(
        self, user_id: int, chat_id: int, text: str
    ) -> str:
        """Envía un mensaje al opencode server y devuelve la respuesta textual."""
        session_id = await self.ensure_session(user_id, chat_id)

        async with httpx.AsyncClient(timeout=120.0) as client:
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
                return await self.send_message(user_id, chat_id, text)

            resp.raise_for_status()
            data = resp.json()

            parts = data.get("parts", [])
            text_parts = [p["text"] for p in parts if p.get("type") == "text"]
            return "\n".join(text_parts) if text_parts else "Entendido."

    async def health(self) -> bool:
        """Verifica si el servidor opencode está accesible."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/global/health", headers=self.headers)
                return resp.status_code == 200
        except Exception:
            return False

    async def reset_session(self) -> None:
        """Elimina la sesión actual para empezar de nuevo."""
        if self.session_id:
            try:
                async with httpx.AsyncClient() as client:
                    await client.delete(
                        f"{self.base_url}/session/{self.session_id}",
                        headers=self.headers,
                    )
            except Exception:
                pass
            self.session_id = None
