from __future__ import annotations

from pathlib import Path
import sys

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.traceback import install

from .models import Config
from .questions import read_questions
from . import templates

import click
from importlib.metadata import version


install()

CONFIG_PATH = "./faq.yml"
QUESTIONS_PATH = "./questions"
TEMPLATES_PATH = ".faq"
FAQ_PATH = "./FAQ.md"
FAQ_URL = "https://github.com/willmcgugan/faqtory/blob/main/FAQ.md"


QUESTIONS_README = """
# Questions

Your questions should go in this directory.

Question files should be named with the extension ".question.md".

"""

FAQ_TEMPLATE = """
# Frequently Asked Questions 

{%- for question in questions %}
- [{{ question.title }}](#{{ question.slug }})
{%- endfor %}


{%- for question in questions %}

<a name="{{ question.slug }}"></a>
## {{ question.title }}

{{ question.body }}

{%- endfor %}

<hr>

Generated by [FAQtory](https://github.com/willmcgugan/faqtory)
"""

SUGGEST_TEMPLATE = """\
{%- if questions -%}
{% if questions|length == 1 %}
We found the following entry in the [FAQ]({{ faq_url }}) which you may find helpful:
{%- else %}
We found the following entries in the [FAQ]({{ faq_url }}) which you may find helpful:
{%- endif %}

{% for question in questions %}
- [{{ question.title }}]({{ faq_url }}#{{ question.slug }})
{%- endfor %}

Feel free to close this issue if you found an answer in the FAQ. Otherwise, please give us a little time to review.

{%- else -%}
Thank you for your issue. Give us a little time to review it.

PS. You might want to check the [FAQ]({{ faq_url }}) if you haven't done so already.
{%- endif %}

This is an automated reply, generated by [FAQtory](https://github.com/willmcgugan/faqtory)
"""


@click.group()
@click.version_option(version("faqtory"))
def run():
    pass


@run.command()
@click.option(
    "-c", "--config", help="Path to config file", default=CONFIG_PATH, metavar="PATH"
)
@click.option(
    "--questions", help="Path to questions", default=QUESTIONS_PATH, metavar="PATH"
)
@click.option(
    "--templates", help="Path to templates", default=TEMPLATES_PATH, metavar="PATH"
)
@click.option(
    "--output", help="Path to generated FAQ", default=FAQ_PATH, metavar="PATH"
)
@click.option("--faq-url", help="FAQ URL", default=FAQ_URL, metavar="PATH")
@click.option(
    "--overwrite/-no-overwrite",
    help="Overwrite files if they exist",
    default=False,
)
def init(
    config: str,
    questions: str,
    templates: str,
    output: str,
    faq_url: str,
    overwrite: bool,
) -> None:
    """Initialise a repository for FAQtory"""
    console = Console()
    error_console = Console(stderr=True)

    DEFAULT_CONFIG = f"""\
# FAQtory settings

faq_url: "{faq_url}" # Replace this with the URL to your FAQ.md!

questions_path: "{questions}" # Where questions should be stored
output_path: "{output}" # Where FAQ.md should be generated 
templates_path: "{templates}" # Path to templates\
"""

    def write_path(path: Path, text: str) -> bool:
        try:
            with path.open("w" if overwrite else "x") as write_file:
                write_file.write(text)
        except FileExistsError:
            error_console.print(
                f"[red]⚠[/] File {str(path)!r} exists, use [b]--overwrite[/b] to update"
            )
            return False
        except Exception as error:
            error_console.print(f"[red]⚠[/] Unable to write {path}; {error}")
            return False

        console.print(f"[green]✔[/] Wrote {str(path)!r}")
        return True

    def make_directory(path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as error:
            error_console.print(f"unable to create {str(path)!r} directory; {error}")
            return False
        console.print(f"[green]✔[/] Directory {str(path)!r} created (or exists)")
        return True

    if write_path(Path(config), DEFAULT_CONFIG):
        console.print(
            Panel(
                Syntax(DEFAULT_CONFIG, "yaml", line_numbers=True, word_wrap=True),
                title=config,
            ),
        )

    make_directory(Path(questions))
    make_directory(Path(templates))

    readme_path = Path(questions) / "README.md"
    write_path(readme_path, QUESTIONS_README)
    write_path(Path(templates) / "FAQ.md", FAQ_TEMPLATE)
    write_path(Path(templates) / "suggest.md", SUGGEST_TEMPLATE)


@run.command()
@click.option(
    "-c",
    "--config",
    help="Path to config file",
    default=CONFIG_PATH,
    metavar="PATH",
)
@click.option("-o", "--output", help="Path to output, or - for stdout", default="")
def build(config: str, output: str) -> None:
    """Build FAQ.md"""
    console = Console(stderr=True)
    config_data = Config.read(Path(config))
    questions = read_questions(config_data.questions_path)

    faq = templates.render_faq(config_data.templates_path, questions=questions)

    faq_path = output or config_data.output_path

    if faq_path == "-":
        print(faq)
    else:
        try:
            Path(faq_path).write_text(faq)
        except OSError as error:
            console.print("[red]⚠[/] failed to write faq;", error)
            sys.exit(-1)
        else:
            console.print(
                f'[green]✔[/] wrote FAQ with {len(questions)} questions to "{faq_path}"'
            )


@run.command()
@click.argument("query")
@click.option(
    "-c", "--config", help="Path to config file", default=CONFIG_PATH, metavar="PATH"
)
def suggest(query: str, config: str) -> None:
    """Suggest FAQ entries"""
    config_data = Config.read(Path(config))
    questions = read_questions(config_data.questions_path)

    scored_results = [(question.match(query), question) for question in questions]
    scored_results.sort(key=lambda result: result[0])

    results = [question for ratio, question in scored_results if ratio > 50]

    suggest = templates.render_suggest(
        config_data.templates_path,
        questions=results,
        faq_url=config_data.faq_url,
    )
    print(suggest)
