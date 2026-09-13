"""Transcode a generated WAV fixture into small MP3 and audio-only MP4 files."""

from __future__ import annotations

import sys
from pathlib import Path

import av
from av.audio.resampler import AudioResampler


def transcode(source: Path, destination: Path, codec: str) -> None:
    with av.open(str(source), mode="r") as input_container:
        input_stream = input_container.streams.audio[0]
        with av.open(str(destination), mode="w") as output_container:
            output_stream = output_container.add_stream(codec, rate=16_000)
            output_stream.layout = "mono"
            output_stream.bit_rate = 64_000
            resampler = AudioResampler(format="fltp", layout="mono", rate=16_000)

            for frame in input_container.decode(input_stream):
                frame.pts = None
                for converted in resampler.resample(frame):
                    for packet in output_stream.encode(converted):
                        output_container.mux(packet)
            for converted in resampler.resample(None):
                for packet in output_stream.encode(converted):
                    output_container.mux(packet)
            for packet in output_stream.encode(None):
                output_container.mux(packet)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: transcode_fixture.py SOURCE.wav OUTPUT_DIRECTORY")
    source = Path(sys.argv[1]).resolve()
    output_directory = Path(sys.argv[2]).resolve()
    if not source.is_file() or source.suffix.lower() != ".wav":
        raise SystemExit("source must be an existing WAV file")
    output_directory.mkdir(parents=True, exist_ok=True)
    transcode(source, output_directory / "spoken-english.mp3", "libmp3lame")
    transcode(source, output_directory / "spoken-english.mp4", "aac")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
