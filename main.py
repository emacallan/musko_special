import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from datastar_py.consts import ElementPatchMode
from datastar_py.fastapi import (
    DatastarResponse,
    ReadSignals,
)
from datastar_py.fastapi import (
    ServerSentEventGenerator as SSE,
)
from datastar_py.sse import DatastarEvent
from fastapi import FastAPI, Request
from fastapi.datastructures import State
from fastapi.staticfiles import StaticFiles
from minijinja import Environment
from starlette.responses import HTMLResponse

# from predator_cattle.state import State
from predator_cattle.templates import CorrectCode, Home, template_loader

state = {}


from predator_cattle.templates import typewriter_words


@asynccontextmanager
async def lifespan(app: FastAPI):
    env = Environment(loader=template_loader)
    env.reload_before_render = True
    env.add_filter("typewriter", typewriter_words)
    yield dict(env=env)


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

    await asyncio.sleep(0.5)

    text = typewriter_words(
        "This is some text that appears in a very cool fashion. "
        "Lorem ipsum dolor sit amet consectetur adipisicing elit. Impedit aliquid facere nobis odio explicabo? Quisquam non iusto unde? Doloribus quaerat quidem sunt alias molestias eligendi at facere expedita? Amet, explicabo.",
    )

    env: Environment = request.state._state["env"]

    yield SSE.patch_elements(
        CorrectCode().render(request),
        # env.render_str(text),
        selector="#content-inner",
        mode=ElementPatchMode.REPLACE,
        use_view_transition=True,
    )


@app.post("/launch-code")
async def launch_verify(request: Request, signals: ReadSignals):
    print(signals)
    if signals is None:
        return

    if signals.get("launchCode") == "answ":
        return DatastarResponse(successful(request))

    return DatastarResponse(SSE.patch_signals(dict(launchCode="")))
