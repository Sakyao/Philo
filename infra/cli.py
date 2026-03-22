import os
import sys
import select
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markdown import Markdown


class PhiloCli(object):
    def __init__(self, pcfg):
        self.pcfg = pcfg
        self.cliDir: Path = self.pcfg.workspace / "cli"
        self.cliDir.mkdir(parents=True, exist_ok=True)
        self.cliHistoryFile = self.cliDir / pcfg.cfgname
        self.console = Console()
        self.promptSession = None
        self.savedTermiosAttrs = None

    def initPromptSession(self):
        try:
            import termios
            self.savedTermiosAttrs = termios.tcgetattr(sys.stdin.fileno())
        except Exception:
            pass
        self.promptSession = PromptSession(
            history=FileHistory(str(self.cliHistoryFile)),
            enable_open_in_editor=False,
            multiline=False,
        )

    def restoreTerminal(self):
        if self.savedTermiosAttrs is None:
            return
        try:
            import termios
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.savedTermiosAttrs)
        except Exception:
            pass

    def flushPendingTtyInput(self):
        try:
            fd = sys.stdin.fileno()
            if not os.isatty(fd):
                return
        except Exception:
            return
        try:
            import termios
            termios.tcflush(fd, termios.TCIFLUSH)
            return
        except Exception:
            pass
        try:
            while True:
                ready, _, _ = select.select([fd], [], [], 0)
                if not ready:
                    break
                if not os.read(fd, 4096):
                    break
        except Exception:
            return

    def print(self, content):
        self.console.print(content)

    def renderMarkdown(self, content):
        if content is None:
            content = "(empty)"
        body = Markdown(content)
        self.console.print()
        self.console.print(f"[cyan]Philo[/cyan]")
        self.console.print(body)
        self.console.print()

    def thinkingContext(self):
        return self.console.status("[dim]Philo is thinking...[/dim]", spinner="dots")

    async def readInteractiveInput(self) -> str:
        try:
            with patch_stdout():
                input = await self.promptSession.prompt_async(HTML("<b fg='ansiblue'>You:</b> "))
                return input.strip()
        except EOFError as exc:
            raise KeyboardInterrupt from exc
