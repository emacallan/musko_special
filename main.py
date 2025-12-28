from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TypedDict
from fastapi import FastAPI, Request
from fastapi.datastructures import State
from minijinja import Environment
from starlette.responses import HTMLResponse

# from predator_cattle.state import State
from predator_cattle.templates import Home, template_loader


state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield dict(env=Environment(loader=template_loader))

app = FastAPI(lifespan=lifespan)


@app.get("/")
async def home(request: Request):
    return HTMLResponse(Home().render(request))
