import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time

from datastar_py.consts import ElementPatchMode
from datastar_py.fastapi import (
    DatastarResponse,
    ReadSignals,
)
from datastar_py.fastapi import (
    ServerSentEventGenerator as SSE,
)
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from minijinja import Environment
from pydantic import BaseModel
from starlette.responses import HTMLResponse

# from predator_cattle.state import State
from predator_cattle.templates import (
    CoordinatesRequest,
    CorrectCode,
    Home,
    template_loader,
)

from predator_cattle.templates import typewriter_words


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Broadcaster:
    """Pub/sub broadcaster - all subscribers receive all messages."""
    
    def __init__(self):
        self._subscribers: dict[str, asyncio.Queue] = {}
    
    def subscribe(self, client_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[client_id] = queue
        logging.info(f"Subscriber {client_id} added, total: {len(self._subscribers)}")
        return queue
    
    def unsubscribe(self, client_id: str):
        if client_id in self._subscribers:
            del self._subscribers[client_id]
            logging.info(f"Subscriber {client_id} removed, total: {len(self._subscribers)}")
    
    async def broadcast(self, message: str):
        logging.info(f"Broadcasting to {len(self._subscribers)} subscribers: {message}")
        for client_id, queue in self._subscribers.items():
            logging.info(f"Putting message in queue for {client_id}")
            await queue.put(message)
    
    def shutdown(self):
        for queue in self._subscribers.values():
            queue.shutdown(immediate=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    env = Environment(loader=template_loader)
    env.reload_before_render = True
    env.add_filter("typewriter", typewriter_words)
    broadcaster = Broadcaster()
    shutdown_event = asyncio.Event()
    active_tasks: set[asyncio.Task] = set()
    logging.info("Broadcaster initialized")
    yield dict(env=env, broadcaster=broadcaster, shutdown_event=shutdown_event, active_tasks=active_tasks)
    logging.info("Stopping")
    shutdown_event.set()
    # Cancel all active streaming tasks
    for task in active_tasks:
        task.cancel()
    if active_tasks:
        await asyncio.gather(*active_tasks, return_exceptions=True)
    broadcaster.shutdown()
    logging.info("Shutdown complete")


app = FastAPI(lifespan=lifespan)

static = Path.home() / ".local/js"

app.mount("/static/", StaticFiles(directory=static))


@app.get("/")
async def home(request: Request):
    return HTMLResponse(Home().render(request))


async def successful(request: Request):
    yield SSE.patch_signals(dict(launchCode="", status="active"))
    yield SSE.patch_elements(
        '<span id="status-indicator" class="status-indicator-active">',
        selector="#status-indicator",
    )

    correct_code = CorrectCode().render(request)
    logger.info(correct_code)

    yield SSE.patch_elements(
        correct_code,
        selector="#content-input",
        mode=ElementPatchMode.INNER,
        use_view_transition=True,
    )

    coordinates_request = CoordinatesRequest().render(request)
    logging.info(coordinates_request)

    yield SSE.patch_elements(
        coordinates_request,
        selector="#content-input",
        mode=ElementPatchMode.APPEND,
        use_view_transition=True,
    )

async def dia(messages: asyncio.Queue, shutdown_event: asyncio.Event, client_id: str):
    logging.info("Dialog generator started, waiting for messages")
    
    while not shutdown_event.is_set():
        try:
            message = await asyncio.wait_for(messages.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        except asyncio.QueueShutDown:
            logging.info("Queue shut down")
            break
        else:
            logging.info(f"Sending message to client: {client_id} {message}")
            # Use unique id to force browser to see this as a new element and trigger animation
            unique_id = int(time.time() * 1000)
            yield SSE.patch_elements(
                f'<p id="msg-{unique_id}">{message}</p>',
                selector="#content-dialog",
                mode=ElementPatchMode.INNER,
            )
            await asyncio.sleep(0.2)


@app.post("/launch-code")
async def launch_verify(request: Request, signals: ReadSignals):
    print(signals)
    if signals is None:
        return

    if signals.get("launchCode") == "answ":
        return DatastarResponse(successful(request))

    return DatastarResponse(SSE.patch_signals(dict(launchCode="")))


@app.get("/dialog")
async def dialog(request: Request):
    broadcaster: Broadcaster = request.state._state["broadcaster"]
    shutdown_event: asyncio.Event = request.state._state["shutdown_event"]
    client_id = str(id(request))
    
    logging.info(f">>> Dialog endpoint hit by {client_id}")
    
    async def generate():
        logging.info(f">>> Generator started for {client_id}")
        # Subscribe inside the generator so it happens when streaming starts
        messages = broadcaster.subscribe(client_id)
        
        try:
            async for event in dia(messages, shutdown_event, client_id):
                yield event
        except asyncio.CancelledError:
            logging.info(f">>> Client {client_id} cancelled")
        finally:
            logging.info(f">>> Finally block for {client_id}")
            # broadcaster.unsubscribe(client_id)
    
    return DatastarResponse(generate())

class NewMessage(BaseModel):
    message: str

@app.post("/api/v1/add-message")
async def add_message(request: Request, message: NewMessage):
    logging.info(message)
    broadcaster: Broadcaster = request.state._state["broadcaster"]
    await broadcaster.broadcast(message.message)
    return Response(status_code=201)

