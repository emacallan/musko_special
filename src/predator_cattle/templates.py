from pathlib import Path
from typing import ClassVar, Unpack
from fastapi import Request
from pydantic import BaseModel, ConfigDict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


TEMPLATE_DIR = Path("templates")

logger.info(TEMPLATE_DIR)


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
        return request.state._state["env"].render_template(self._template.name, **self.model_dump(**kwargs))

class Home(TemplateBase, template=Path("home.html")):
    pass
