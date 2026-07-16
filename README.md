# TelegramBot — Mini Asistente Personal con IA

Bot de Telegram que funciona como un asistente personal con **tareas**, **listas de la compra** y **recordatorios programados**, potenciado por **IA** a través de [opencode server](https://opencode.ai).

---

## Características

- **IA integrada** — conversación fluida en lenguaje natural; no necesitas comandos
- **Ingredientes de recetas** — pregúntale "¿qué lleva una paella?" y los añade a tu lista
- **Recomendaciones inteligentes** — sugiere horarios, rutinas, prioridades basadas en sueño y productividad
- **Tareas** — crear, listar, completar y borrar tareas con prioridad
- **Listas de la compra** — crear listas, añadir productos, marcar como comprados
- **Recordatorios programados** — avisa en el momento exacto que configures
- **Comandos tradicionales** — también disponibles si prefieres usarlos

---

## Requisitos

- Python 3.10+
- Un token de bot de Telegram (obtener de [@BotFather](https://t.me/BotFather))
- [opencode](https://opencode.ai) instalado globalmente (`npm install -g opencode-ai`)
- Un provider configurado en opencode (Zen, OpenAI, Claude, etc.)

---

## Instalación

```bash
# 1. Clonar o copiar el proyecto
cd TelegramBot

# 2. Crear entorno virtual
python -m venv .venv

# 3. Activar el entorno virtual
# Windows:
.venv\Scripts\Activate.ps1
# Linux/Mac:
source .venv/bin/activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Configurar token
# Edita .env y pon tu token:
# TELEGRAM_BOT_TOKEN=tu_token_aqui
```

---

## Configuración

1. Habla con [@BotFather](https://t.me/BotFather) en Telegram y crea un bot con `/newbot`
2. Copia el token en `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
3. Asegúrate de tener opencode instalado y con un provider configurado:
   ```bash
   opencode --version
   ```

---

## Ejecutar

### 1. Iniciar opencode server (en una terminal)

```bash
opencode serve
```

### 2. Iniciar el bot de Telegram (en otra terminal)

```bash
python bot.py
```

---

## Uso

### Modo IA (recomendado)

Simplemente escribe lo que necesites en lenguaje natural:

| Si dices... | El bot hará... |
|-------------|----------------|
| "Crea una tarea para limpiar el coche" | Crea una tarea con prioridad normal |
| "Añade leche, pan y huevos a la lista" | Añade productos a tu lista de la compra |
| "¿Qué tareas tengo?" | Muestra tus tareas pendientes |
| "Recuérdame lo del médico mañana a las 9" | Programa un recordatorio |
| "¿Qué ingredientes lleva una pizza margarita?" | Te dice los ingredientes y los añade a tu lista |
| "Recomiéndame una rutina para mañana" | Sugiere horarios asumiendo 8h de sueño |

### Comandos tradicionales

Si prefieres los comandos clásicos, también funcionan:

| Comando | Descripción |
|---------|-------------|
| `/tarea` | Crear tarea nueva (guiado) |
| `/tareas` | Ver tareas pendientes |
| `/hecho ID` | Marcar tarea como completada |
| `/borrar ID` | Eliminar tarea |
| `/lista` | Crear lista nueva (guiado) |
| `/listas` | Ver todas tus listas |
| `/ver ID` | Ver productos de una lista |
| `/anadir ID producto` | Añadir producto rápido |
| `/comprado ID` | Marcar item como comprado |
| `/limpiar ID` | Borrar items comprados |
| `/recordar` | Crear recordatorio (guiado) |
| `/recordatorios` | Ver recordatorios activos |
| `/cancelar ID` | Cancelar recordatorio |
| `/start` | Bienvenida |
| `/help` | Ayuda completa |

---

## Estructura del proyecto

```
TelegramBot/
├── bot.py                  # Punto de entrada
├── requirements.txt        # Dependencias
├── .env                    # Token del bot (no commitear)
├── .env.example            # Plantilla de ejemplo
├── opencode.jsonc          # Config de opencode (MCP tools)
│
├── bot/
│   ├── __init__.py
│   ├── database.py         # SQLite: tareas, listas, recordatorios
│   ├── handlers.py         # Handlers de comandos y conversación
│   ├── ai_client.py        # Cliente HTTP para opencode server
│   └── mcp_server.py       # MCP server: expone la DB como tools para la IA
│
└── data/
    └── bot.db              # Base de datos (auto-creada)
```

---

## Arquitectura

```
Telegram ──→ python-telegram-bot ──→ handlers.handle_message
                                             │
                                             ▼
                                    opencode server (HTTP)
                                             │
                                    ┌────────┴────────┐
                                    ▼                 ▼
                                 IA (Claude/etc)   MCP tools
                                                      │
                                                      ▼
                                                 database.py (SQLite)
```

| Componente | Responsabilidad |
|------------|----------------|
| `bot.py` | Configuración, registro de handlers, arranque |
| `bot/handlers.py` | Handler principal de IA + comandos legacy |
| `bot/ai_client.py` | Cliente HTTP para el opencode server |
| `bot/mcp_server.py` | Expone la DB como MCP tools para la IA |
| `bot/database.py` | CRUD SQLite: tareas, listas, items, recordatorios |
| `opencode.jsonc` | Configura MCP server para este proyecto |

---

## Stack tecnológico

- **python-telegram-bot** — librería oficial de Telegram para Python
- **opencode server** — servidor headless de opencode para conectar con IA
- **MCP (Model Context Protocol)** — protocolo estándar para herramientas de IA
- **SQLite** — persistencia embebida, sin configuración externa
- **httpx** — cliente HTTP asíncrono para conectar con opencode
