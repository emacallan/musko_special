from pathlib import Path
from typing import ClassVar, Unpack
from fastapi import Request
from pydantic import BaseModel, ConfigDict
from minijinja import Markup, escape
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


TEMPLATE_DIR = Path("templates")

logger.info(TEMPLATE_DIR)


def typewriter_words(text: str, delay_step: float = 0.05) -> Markup:
    """Wrap each word in a span with staggered animation delay."""
    words = re.split(r"(\s+)", text)
    result = []
    word_index = 0
    for part in words:
        if part.strip():
            delay = word_index * delay_step
            result.append(
                f'<span class="tw-word" style="animation-delay: {delay:.2f}s">{escape(part)}</span>'
            )
            word_index += 1
        else:
            result.append(part)
    return Markup("".join(result))


def template_loader(template: str) -> str | None:
    logging.info(template)

    tmpl = TEMPLATE_DIR / template

    if not tmpl.exists() or tmpl.is_dir():
        return

    with open(tmpl) as file:
        return file.read()


class TemplateBase(BaseModel):
    _template: ClassVar[Path]

    def __init_subclass__(cls, *, template: Path, **kwargs: Unpack[ConfigDict]):
        cls._template = TEMPLATE_DIR / template

        return super().__init_subclass__(**kwargs)

    def render(self, request: Request, **kwargs) -> str:
        logger.info(f"template name: {self._template.name}")
        return request.state._state["env"].render_template(
            self._template.name, **self.model_dump(**kwargs)
        )


class Home(TemplateBase, template=Path("home.html")):
    pass


class CorrectCode(TemplateBase, template=Path("correct_code.html")):
    def render(self, request: Request, **kwargs) -> str:
        text = request.state._state["env"].render_str(
            typewriter_words(self._template.read_text())
        )
        return f'<div class="terminal-output">{text}</div>'
