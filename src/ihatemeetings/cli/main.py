from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from ihatemeetings import __version__
from ihatemeetings.asr.models import MODELS, download_model, is_model_cached, model_cache_dir
from ihatemeetings.config.defaults import RuntimeConfig
from ihatemeetings.errors import IHMError
from ihatemeetings.pipeline import run_transcription
from ihatemeetings.platform.doctor import run_doctor


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    normalized_argv = normalize_argv(list(argv) if argv is not None else sys.argv[1:])
    try:
        args = parser.parse_args(normalized_argv)
    except SystemExit as exc:
        return int(exc.code)
    configure_logging(verbose=args.verbose, debug=args.debug)

    try:
        command = args.command
        if command == "doctor":
            return run_doctor()
        if command == "models":
            return handle_models(args)
        if command == "speakers":
            return handle_speakers(args)
        if command == "transcribe":
            return handle_transcribe(args)
    except IHMError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if exc.remediation:
            print(f"Fix: {exc.remediation}", file=sys.stderr)
        return 1

    parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ihm",
        description="IHateMeetings: local-first meeting transcription.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--verbose", action="store_true", help="Show verbose progress output.")
    parser.add_argument("--debug", action="store_true", help="Show debug diagnostics.")

    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="Check local runtime dependencies.")
    doctor.set_defaults(command="doctor")

    transcribe = subparsers.add_parser("transcribe", help="Transcribe a media file.")
    add_transcribe_arguments(transcribe)
    transcribe.set_defaults(command="transcribe")

    models = subparsers.add_parser("models", help="Manage local model metadata.")
    model_subcommands = models.add_subparsers(dest="models_command", required=True)
    model_subcommands.add_parser("list", help="List configured model profiles.")
    model_download = model_subcommands.add_parser(
        "download", help="Explicitly download a supported ASR model."
    )
    model_download.add_argument("model", choices=tuple(MODELS))
    models.set_defaults(command="models")

    speakers = subparsers.add_parser("speakers", help="Manage local speaker identities.")
    speaker_subcommands = speakers.add_subparsers(dest="speakers_command", required=True)
    speaker_subcommands.add_parser("list", help="List local speaker identities.")
    speakers.set_defaults(command="speakers")

    return parser


def add_transcribe_arguments(parser: argparse.ArgumentParser, positional: bool = True) -> None:
    if positional:
        parser.add_argument("input", type=Path, help="Input audio or video file.")
    parser.add_argument(
        "--profile",
        choices=("fast", "balanced", "accurate"),
        default=None,
        help="Execution profile. Defaults to automatic selection.",
    )
    parser.add_argument("--language", help="Expected language, for example 'it'.")
    parser.add_argument("--model", help="Model name or path to a local CTranslate2 model.")
    parser.add_argument(
        "--device", choices=("auto", "cpu", "cuda"), default=None, help="Inference device."
    )
    parser.add_argument("--compute-type", help="CTranslate2 compute type, such as int8.")
    parser.add_argument(
        "--output-dir", type=Path, default=None, help="Output root directory (default: output)."
    )
    parser.add_argument("--config", type=Path, help="Optional configuration file.")
    parser.add_argument("--context", type=Path, help="Optional meeting context file.")
    parser.add_argument("--anchors", type=Path, help="Optional anchor mapping YAML file.")
    parser.add_argument("--glossary", type=Path, help="Optional glossary YAML file.")


def handle_transcribe(args: argparse.Namespace) -> int:
    input_path = Path(args.input) if args.input else None
    if input_path is None:
        print("No input file provided. Use 'ihm transcribe FILE' or 'ihm FILE'.")
        return 2
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 2
    if not input_path.is_file():
        print(f"Input is not a file: {input_path}")
        return 2
    phase2_options = [args.context, args.anchors, args.glossary]
    if any(phase2_options):
        print("Context, anchors and glossary processing starts after Phase 1.")
        return 2

    config = RuntimeConfig.from_sources(
        profile=args.profile,
        language=args.language,
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
        output_dir=args.output_dir,
        config_file=args.config,
    )
    print("IHateMeetings")
    print()
    run_transcription(input_path, config)
    return 0


def handle_models(args: argparse.Namespace) -> int:
    if args.models_command == "list":
        print("IHateMeetings model profiles")
        print()
        for name, spec in MODELS.items():
            status = "cached" if is_model_cached(name) else "not downloaded"
            print(f"{name:<18} {spec.approximate_size:<14} {status}")
        print()
        print(f"Cache: {model_cache_dir()}")
        print("No model weights are bundled or downloaded automatically.")
        return 0
    if args.models_command == "download":
        spec = MODELS[args.model]
        print(f"Downloading {spec.name} from {spec.repository} ({spec.approximate_size}).")
        print("This command requires Internet access. Meeting media is never uploaded.")
        path = download_model(args.model)
        print(f"Model ready: {path}")
        return 0
    return 2


def handle_speakers(args: argparse.Namespace) -> int:
    if args.speakers_command == "list":
        print("No local speaker database has been initialized.")
        return 0
    return 2


def configure_logging(verbose: bool = False, debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def normalize_argv(argv: list[str] | None) -> list[str] | None:
    if argv is None or not argv:
        return argv
    commands = {"doctor", "models", "speakers", "transcribe"}
    first = argv[0]
    if first.startswith("-") or first in commands:
        return argv
    return ["transcribe", *argv]
