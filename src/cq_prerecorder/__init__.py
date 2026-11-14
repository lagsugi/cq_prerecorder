import argparse
import shutil
import struct
import subprocess
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .selection import Terminal, select_mode, select_slots


@dataclass(frozen=True)
class Radio:
    number: str
    sample_rate: int
    firmware: str
    recording_date: str


# Match the format and metadata from each radio's Voice TX recording.
RADIOS = (
    Radio("7300", 8000, "1.42", "2000-07-05"),
    Radio("7610", 16000, "1.30", "2026-04-25"),
)


def convert_pcm(ffmpeg: str, source: Path, sample_rate: int) -> bytes:
    result = subprocess.run(
        [
            ffmpeg, "-nostdin", "-v", "error", "-xerror", "-i", str(source),
            "-map", "0:a:0", "-ac", "1", "-ar", str(sample_rate),
            "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
        ],
        capture_output=True,
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(message or f"FFmpeg が終了コード {result.returncode} を返しました。")
    if not result.stdout:
        raise ValueError("音声データが空です。")
    return result.stdout


def riff_chunk(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<I", len(payload)) + payload + b"\0" * (len(payload) % 2)


def build_voice_tx_wav(pcm: bytes, name: str, radio: Radio) -> bytes:
    model = f"IC-{radio.number}"
    title = f"{model} Voice TX Data {name[:16]:16}"
    info = b"INFO" + b"".join(
        riff_chunk(tag, value.encode("ascii", errors="replace") + b"\0")
        for tag, value in (
            (b"ICRD", radio.recording_date),
            (b"INAM", title),
            (b"ISFT", f"{model} Ver{radio.firmware}"),
        )
    )
    # 16-bit mono PCM. Icom recordings place LIST/INFO after data.
    fmt = struct.pack("<HHIIHH", 1, 1, radio.sample_rate, radio.sample_rate * 2, 2, 16)
    return riff_chunk(
        b"RIFF",
        b"WAVE" + riff_chunk(b"fmt ", fmt) + riff_chunk(b"data", pcm) + riff_chunk(b"LIST", info),
    )


def export_wavs(
    ffmpeg: str, input_dir: Path, files: list[tuple[str, Path]], *, sdcard: bool,
) -> None:
    with ExitStack() as stack:
        files_to_publish = []
        for radio in RADIOS:
            output_dir = Path(f"wav_IC{radio.number}")
            if output_dir.resolve() == input_dir.resolve():
                raise ValueError(f"{output_dir} と {input_dir} が同じフォルダーです。")
            destination = output_dir / "sdcard" if sdcard else output_dir
            if sdcard and destination.resolve() != output_dir.resolve() / "sdcard":
                raise ValueError(f"{destination} に別のフォルダーがリンクされています。")
            destination.mkdir(parents=True, exist_ok=True)
            staging_dir = Path(stack.enter_context(TemporaryDirectory(dir=destination)))
            staged_sources: dict[Path, Path] = {}
            print(f"IC-{radio.number} 向けに変換中…", flush=True)
            for filename, source in files:
                staged = staging_dir / filename
                target = destination / filename
                try:
                    if target.is_dir():
                        raise IsADirectoryError(f"{target} はフォルダーです。")
                    if source in staged_sources:
                        shutil.copyfile(staged_sources[source], staged)
                    else:
                        pcm = convert_pcm(ffmpeg, source, radio.sample_rate)
                        staged.write_bytes(build_voice_tx_wav(pcm, source.stem, radio))
                        staged_sources[source] = staged
                except (OSError, ValueError) as error:
                    raise ValueError(f"{source} → {target} の変換に失敗しました。\n{error}") from error
                files_to_publish.append((staged, target))

        for staged, target in files_to_publish:
            staged.replace(target)
        for radio in RADIOS:
            destination = Path(f"wav_IC{radio.number}")
            if sdcard:
                destination /= "sdcard"
            print(f"{destination} に {len(files)} 件の WAV を出力しました。")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="submitted_wav の WAV を IC-7300／IC-7610 の Voice TX 用に変換します。",
    )
    parser.add_argument(
        "--convert-only",
        action="store_true",
        help="メニューを開かずに、全音声を元のファイル名で変換します。",
    )
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        parser.error("ffmpeg を PATH に追加してください。")

    input_dir = Path("submitted_wav")
    if not input_dir.is_dir():
        parser.error(f"{input_dir} フォルダーのある場所で実行してください。")
    sources = sorted(
        path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".wav"
    )
    if not sources:
        parser.error(f"{input_dir} に WAV ファイルがありません。")

    files = [(source.name, source) for source in sources]
    sdcard = False
    if not args.convert_only:
        try:
            with Terminal() as terminal:
                mode = select_mode(terminal)
                if mode is None:
                    return
                if mode == "sdcard":
                    slots = select_slots(terminal, sources)
                    if slots is None:
                        return
                    files = [(f"voicetx{i}.wav", source) for i, source in slots.items()]
                    sdcard = True
        except (EOFError, KeyboardInterrupt):
            return

    try:
        export_wavs(ffmpeg, input_dir, files, sdcard=sdcard)
    except (OSError, ValueError) as error:
        parser.exit(1, f"WAV の出力に失敗しました。\n{error}\n")
