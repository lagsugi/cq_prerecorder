import os
import shutil
import sys
from itertools import zip_longest
from pathlib import Path
from unicodedata import category, east_asian_width


SLOT_COUNT = 8


class Terminal:
    def __init__(self) -> None:
        self.interactive = sys.stdin.isatty() and sys.stdout.isatty()
        self.arrow_keys = self.interactive and os.name == "nt"
        self.redraw = False

    def __enter__(self) -> Terminal:
        if self.arrow_keys:
            import ctypes
            from ctypes import wintypes

            console = ctypes.WinDLL("kernel32", use_last_error=True)
            console.GetStdHandle.argtypes = [wintypes.DWORD]
            console.GetStdHandle.restype = wintypes.HANDLE
            console.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            console.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            self.console = console
            self.handle = console.GetStdHandle(wintypes.DWORD(-11))
            self.mode = wintypes.DWORD()
            self.redraw = bool(
                console.GetConsoleMode(self.handle, ctypes.byref(self.mode))
                and console.SetConsoleMode(self.handle, self.mode.value | 4)
            )
        elif self.interactive:
            self.redraw = os.environ.get("TERM", "dumb") != "dumb"

        if self.redraw:
            print("\x1b[?1049h\x1b[?25l", end="", flush=True)
        return self

    def __exit__(self, *exc) -> None:
        if self.redraw:
            print("\x1b[?25h\x1b[?1049l", end="", flush=True)
            if os.name == "nt":
                self.console.SetConsoleMode(self.handle, self.mode.value)

    def show(self, lines: list[str]) -> None:
        prefix = "\x1b[H\x1b[2J" if self.redraw else "\n"
        print(prefix + "\n".join(lines), flush=True)

    def highlight(self, label: str, *, selected: bool) -> str:
        return f"\x1b[7m{label}\x1b[0m" if selected and self.redraw else label

    def read(self) -> str:
        if self.arrow_keys:
            import msvcrt

            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):
                return {"H": "up", "P": "down", "K": "left", "M": "right"}.get(msvcrt.getwch(), "")
            if key == "\x03":
                raise KeyboardInterrupt
            if key == "\x1b":
                return "q"
            return "enter" if key == "\r" else key.lower()

        # Line input also works in redirected sessions and terminals without arrow-key handling.
        return input("> ").strip().lower() or "enter"


def select_mode(terminal: Terminal) -> str | None:
    options = [
        ("sdcard", "SDカード用WAVを作る", "T1〜T8 に選んだ音声を両機種の sdcard/ に出力"),
        ("all", "全音声を変換する", "元のファイル名で両機種の出力フォルダーに保存"),
    ]
    selected = 0
    while True:
        lines = ["CQ Prerecorder", ""]
        for index, (_, label, detail) in enumerate(options):
            marker = ">" if index == selected else " "
            label = terminal.highlight(f"{marker} {index + 1}. {label}", selected=index == selected)
            lines.extend((label, f"     {detail}", ""))
        movement = "↑↓ / W・S" if terminal.arrow_keys else "W・S"
        lines.append(f"{movement}  移動     Enter  選択     1・2  直接選択     Q  終了")
        terminal.show(lines)
        key = terminal.read()
        if key in ("up", "down", "w", "s"):
            selected = 1 - selected
        elif key in ("1", "2"):
            return options[int(key) - 1][0]
        elif key == "enter":
            return options[selected][0]
        elif key == "q":
            return None


def fit_cell(value: str, width: int) -> str:
    widths = [
        0 if category(char) in ("Mn", "Me") else (
            2 if east_asian_width(char) in ("F", "W") else 1
        )
        for char in value
    ]
    total = sum(widths)
    if total <= width:
        return value + " " * (width - total)
    used = 0
    for index, char_width in enumerate(widths):
        if used + char_width >= width:
            return value[:index] + "…" + " " * (width - used - 1)
        used += char_width
    return value


def select_slots(terminal: Terminal, sources: list[Path]) -> dict[int, Path] | None:
    slots: dict[int, Path] = {}
    slot = cursor = 0
    message = ""

    while True:
        width, height = shutil.get_terminal_size(fallback=(80, 24))
        left_width = min(32, width // 2)
        right_width = max(16, width - left_width - 5)
        page_size = max(1, min(12, height - 10))
        first = cursor // page_size * page_size
        last = min(len(sources), first + page_size)
        assignments = [
            f"{'>' if index == slot else ' '} T{index + 1}  "
            f"{slots[index].name if index in slots else '未選択'}"
            for index in range(SLOT_COUNT)
        ]
        candidates = [
            f"{'>' if index == cursor else ' '} {index + 1:>3}  {sources[index].name}"
            for index in range(first, last)
        ]
        lines = [
            "SDカード用WAV  |  IC-7300 / IC-7610",
            "",
            f"{fit_cell(f'割り当て  {len(slots)}/{SLOT_COUNT}', left_width)}  │  "
            f"音声候補  {first + 1}–{last} / {len(sources)}",
        ]
        for row, (assignment, candidate) in enumerate(zip_longest(assignments, candidates, fillvalue="")):
            left = terminal.highlight(fit_cell(assignment, left_width), selected=row == slot)
            right = terminal.highlight(fit_cell(candidate, right_width), selected=first + row == cursor)
            lines.append(f"{left}  │  {right}")
        move_slot = "←→ / A・D" if terminal.arrow_keys else "A・D"
        move_source = "↑↓ / W・S" if terminal.arrow_keys else "W・S"
        lines.extend((
            "",
            f"{move_slot}  枠を移動     {move_source}  候補を移動",
            "Enter  割り当て     1〜8  枠を選択     G  選んだ枠を生成     Q  中止",
            message,
        ))
        terminal.show(lines)
        key = terminal.read()
        message = ""
        if key in ("up", "w"):
            cursor = (cursor - 1) % len(sources)
        elif key in ("down", "s"):
            cursor = (cursor + 1) % len(sources)
        elif key in ("left", "a"):
            slot = (slot - 1) % SLOT_COUNT
        elif key in ("right", "d"):
            slot = (slot + 1) % SLOT_COUNT
        elif len(key) == 1 and key in "12345678":
            slot = int(key) - 1
        elif key == "enter":
            slots[slot] = sources[cursor]
            slot = next((index for index in range(SLOT_COUNT) if index not in slots), slot)
        elif key == "g":
            if slots:
                return {index + 1: source for index, source in sorted(slots.items())}
            message = "音声を1枠以上に割り当ててください。"
        elif key == "q":
            return None
        else:
            message = "画面に表示された操作キーを入力してください。"
