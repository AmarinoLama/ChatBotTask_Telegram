# Mister Organizer — Tu asistente personal con IA 🤵‍♂️✨

Bot de Telegram con inteligencia artificial que te ayuda a organizar tu día a día: tareas, lista de la compra, recordatorios y mucho más. Todo en lenguaje natural y con mucho humor.

---

## Características 🤖

- **IA integrada** — háblale como a un amigo, sin comandos raros
- **Recetas y lista de la compra** — pregúntale una receta y añade los ingredientes automáticamente a tu lista
- **Recomendaciones inteligentes** — sugiere horarios, rutinas y prioridades según tu día
- **Tareas** — crea, lista, completa y borra tareas al toque
- **Listas de la compra** — productos, marcar comprados, limpiar lista
- **Recordatorios** — te avisa cuando le pidas, a la hora que sea
- **Comandos tradicionales** — si eres old school, también funcionan
- **Múltiples usuarios** — cada uno con sus propias cosas
- **Persistencia** — todo en SQLite, nunca se pierde nada

---

## Requisitos prerequisitos 📋

- Python 3.10+
- Token de bot de Telegram ([habla con @BotFather](https://t.me/BotFather))
- [opencode](https://opencode.ai) instalado globalmente (`npm install -g opencode-ai`)
- Un provider de IA en opencode (Zen, Claude, GPT, el que quieras)

---

## Instalación 🚀

```bash
# 1. Clonar o copiar el proyecto
cd TelegramBot

# 2. Entorno virtual (recomendado)
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate   # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Token del bot en .env
# TELEGRAM_BOT_TOKEN=tu_token_aqui
```

---

## Cómo usarlo 🎯

### 1. Arrancar la IA (una terminal)
```bash
opencode serve
```

### 2. Arrancar el bot (otra terminal)

```bash
python bot.py
```

¡Y ya! Háblale a tu bot de Telegram directamente.

---

## Ejemplos de uso 💬

| Lo que dices | Lo que hace |
|---|---|
| "Crea una tarea para limpiar el coche" | Crea la tarea automaticamente 🎯 |
| "Añade leche, huevos y pan a la lista" | Los mete en tu lista de la compra 🛒 |
| "¿Qué tareas tengo?" | Te enumera las pendientes 📋 |
| "Recuérdame la reunion del jueves a las 10" | Programa recordatorio para ese día ⏰ |
| "¿Qué lleva una pasta carbonara? Añadelo a la lista" | Te da la receta y mete los ingredientes 🍝 |
| "Recomiéndame un planning para mañana" | Te organiza el día con ✨ estilo Mister Organizer ✨ |

---

## Comandos tradicionales (/help) 📟

| Comando | Qué hace |
|---|---|
| `/tarea` | Crear tarea paso a paso |
| `/tareas` | Ver tareas pendientes |
| `/hecho` ID | Completar tarea |
| `/borrar` ID | Eliminar tarea |
| `/lista` | Crear lista de la compra guiada |
| `/listas` | Ver todas tus listas |
| `/ver` ID | Ver contenido de una lista |
| `/anadir` ID_L. product | Añadir producto rápido a lista |
| `/comprado` ID_ITEM | Marcar un producto como comprado |
| `/limpiar` ID_L. | Borrar productos comprados de una lista |
| `/recordar` | Nuevo recordatorio guiado |
| `/recordatorios` | Ver recordatorios activos |
| `/cancelar` ID | Cancelar recordatorio |

---

## Cómo funciona por dentro ⚙️

```
Tú escribes en Telegram   →   Bot lo manda al opencode server
                                        ↓
                              La IA responde con JSON:
                              {"mensaje": "...", "acciones": [...]}
                                        ↓
                              Bot ejecuta las acciones en la DB
                                        ↓
                              Te llega la respuesta al Telegram
```

| Componente | Su misión |
|---|---|
| `bot.py` | Arranca el tinglado y registra los handlers |
| `bot/handlers.py` | Recibe tu mensaje, lo manda a IA, ejecuta acciones, te responde |
| `bot/ai_client.py` | Habla con opencode server y gestiona los formatos JSON |
| `bot/database.py` | Se encarga de todo el SQLite (crear, leer, actualizar, borrar) |
| `data/bot.db` | Aquí vive todo lo que te guardas (SQLite) |

---

## Árbol del proyecto 🌳

```
TelegramBot/
├── bot.py                  # Punto de entrada (ejecuta el bot)
├── requirements.txt        # Las dependencias que necesita python
├── .env                    # Token del bot (NO se sube a GitHub)
├── .env.example            # Plantilla para que te guíes
│
├── bot/
│   ├── __init__.py         # Paquete python vacío
│   ├── database.py         # CRUD de todo: tareas, listas, recordatorios
│   ├── handlers.py         # Los que procesan los mensajes del usuario
│   └── ai_client.py        # Cliente para IA (opencode server + JSON) + ejecutor de acciones
│
└── data/
    └── bot.db              # Base de datos local (la crea sola al iniciar)
```

---

## Stack tecnológico 🛠️

- **python-telegram-bot** — para que el bot funcione en Telegram como uno más
- **SQLite** — donde guardas todo lo tuyo, sin esfuerzo ni configuración complicada
- **httpx** — para que python hable con el opencode server como si nada, de forma moderna
- **opencode server** — la IA: recibe tu mensaje y vuelve a la acción directamente con JSONs bien formateados"
