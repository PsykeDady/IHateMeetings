from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from ihatemeetings import __version__
from ihatemeetings.alignment.models import (
    ALIGNMENT_MODELS,
    alignment_cache_dir,
    download_alignment_model,
    is_alignment_model_cached,
)
from ihatemeetings.asr.models import MODELS, download_model, is_model_cached, model_cache_dir
from ihatemeetings.config.defaults import RuntimeConfig
from ihatemeetings.diarization.models import (
    COMMUNITY_1,
    diarization_cache_dir,
    download_diarization_model,
    is_diarization_model_cached,
)
from ihatemeetings.errors import IHMError
from ihatemeetings.languages import SUPPORTED_LANGUAGES
from ihatemeetings.pipeline import run_transcription
from ihatemeetings.platform.doctor import run_doctor
from ihatemeetings.review.interactive import format_segment, format_speakers, run_interactive
from ihatemeetings.review.service import ReviewSession
from ihatemeetings.speakers import load_resolution_config, parse_speaker_mapping


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
        if command == "review":
            return handle_review(args)
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
    alignment_download = model_subcommands.add_parser(
        "download-alignment", help="Explicitly download a language alignment model."
    )
    alignment_download.add_argument("language", choices=tuple(ALIGNMENT_MODELS))
    model_subcommands.add_parser(
        "download-diarization",
        help="Explicitly acquire gated pyannote Community-1 assets using HF_TOKEN.",
    )
    models.set_defaults(command="models")

    speakers = subparsers.add_parser("speakers", help="Manage local speaker identities.")
    speaker_subcommands = speakers.add_subparsers(dest="speakers_command", required=True)
    speaker_subcommands.add_parser("list", help="List local speaker identities.")
    speakers.set_defaults(command="speakers")

    review = subparsers.add_parser("review", help="Review an existing transcript without ML.")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    review_list = review_commands.add_parser("list", help="List stable review segment IDs.")
    review_list.add_argument("output", type=Path)
    review_list.add_argument("--unknown-only", action="store_true")
    review_show = review_commands.add_parser("show", help="Inspect one segment or UNKNOWN ID.")
    review_show.add_argument("output", type=Path)
    review_show.add_argument("reference")
    review_speakers = review_commands.add_parser(
        "speakers", help="List original clusters and reviewed identities."
    )
    review_speakers.add_argument("output", type=Path)
    assign_speaker = review_commands.add_parser(
        "assign-speaker", help="Assign a display name to an entire original cluster."
    )
    assign_speaker.add_argument("output", type=Path)
    assign_speaker.add_argument("cluster")
    assign_speaker.add_argument("--name", required=True)
    assign_segment = review_commands.add_parser(
        "assign-segment", help="Override the speaker for one segment."
    )
    assign_segment.add_argument("output", type=Path)
    assign_segment.add_argument("reference")
    _add_assignment_target(assign_segment)
    assign_unknown = review_commands.add_parser(
        "assign-unknown", help="Resolve one original UNKNOWN by SEG or UNK ID."
    )
    assign_unknown.add_argument("output", type=Path)
    assign_unknown.add_argument("reference")
    _add_assignment_target(assign_unknown)
    merge = review_commands.add_parser("merge", help="Merge adjacent active segments.")
    merge.add_argument("output", type=Path)
    merge.add_argument("first")
    merge.add_argument("second")
    _add_assignment_target(merge, required=False)
    delete = review_commands.add_parser("delete", help="Tombstone one reviewed segment.")
    delete.add_argument("output", type=Path)
    delete.add_argument("reference")
    interactive = review_commands.add_parser(
        "interactive", help="Run transactional prompt-based transcript review."
    )
    interactive.add_argument("output", type=Path)
    interactive.add_argument("--unknown-only", action="store_true")
    review.set_defaults(command="review")

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
    parser.add_argument(
        "--language",
        choices=SUPPORTED_LANGUAGES,
        help="Official input language: Italian (it) or English (en).",
    )
    parser.add_argument("--model", help="Model name or path to a local CTranslate2 model.")
    parser.add_argument(
        "--device", choices=("auto", "cpu", "cuda"), default=None, help="Inference device."
    )
    parser.add_argument("--compute-type", help="CTranslate2 compute type, such as int8.")
    parser.add_argument(
        "--align",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable word alignment (default: use it when locally ready).",
    )
    parser.add_argument(
        "--alignment-model", help="Path to a local Transformers CTC alignment model."
    )
    parser.add_argument(
        "--diarize",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable speaker diarization (default: use it when locally ready).",
    )
    parser.add_argument("--diarization-model", help="Path to a prepared local pyannote model.")
    parser.add_argument("--num-speakers", type=_positive_int, help="Exact known speaker count.")
    parser.add_argument("--min-speakers", type=_positive_int, help="Minimum expected speakers.")
    parser.add_argument("--max-speakers", type=_positive_int, help="Maximum expected speakers.")
    parser.add_argument(
        "--speaker",
        action="append",
        default=[],
        metavar='SPEAKER_NN="Name"',
        help="Map a diarization cluster to a verified name; repeat for multiple speakers.",
    )
    parser.add_argument(
        "--speaker-map",
        type=Path,
        help="Optional YAML file containing authoritative cluster-to-identity mappings.",
    )
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
    if args.glossary:
        print("Glossary processing is not supported yet.")
        return 2
    try:
        speaker_mappings = tuple(parse_speaker_mapping(value) for value in args.speaker)
    except ValueError as exc:
        print(f"Invalid --speaker mapping: {exc}.")
        return 2
    clusters = [mapping.cluster for mapping in speaker_mappings]
    if len(clusters) != len(set(clusters)):
        print("Each speaker cluster may be mapped only once.")
        return 2
    if args.num_speakers is not None and (
        args.min_speakers is not None or args.max_speakers is not None
    ):
        print("--num-speakers cannot be combined with --min-speakers or --max-speakers.")
        return 2
    if (
        args.min_speakers is not None
        and args.max_speakers is not None
        and args.min_speakers > args.max_speakers
    ):
        print("--min-speakers cannot be greater than --max-speakers.")
        return 2
    speaker_hints = (args.num_speakers, args.min_speakers, args.max_speakers)
    if args.diarize is False and any(value is not None for value in speaker_hints):
        print("Speaker count hints cannot be used with --no-diarize.")
        return 2
    resolution = load_resolution_config(
        cli_mappings=speaker_mappings,
        speaker_map_path=args.speaker_map,
        anchors_path=args.anchors,
        context_path=args.context,
    )
    if args.diarize is False and resolution.requested:
        print("Speaker resolution options cannot be used with --no-diarize.")
        return 2

    config = RuntimeConfig.from_sources(
        profile=args.profile,
        language=args.language,
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
        align=args.align,
        alignment_model=args.alignment_model,
        diarize=True if resolution.requested else args.diarize,
        diarization_model=args.diarization_model,
        num_speakers=args.num_speakers,
        min_speakers=args.min_speakers,
        max_speakers=args.max_speakers,
        speaker_resolution=resolution,
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
        print()
        print("Alignment models")
        for language, spec in ALIGNMENT_MODELS.items():
            status = "cached" if is_alignment_model_cached(language) else "not downloaded"
            print(f"{language:<18} {spec.approximate_size:<14} {spec.license:<12} {status}")
        print(f"Alignment cache: {alignment_cache_dir()}")
        print()
        print("Diarization model")
        status = "cached" if is_diarization_model_cached() else "not downloaded"
        print(
            f"{COMMUNITY_1.name:<18} {COMMUNITY_1.approximate_size:<48} "
            f"{COMMUNITY_1.license:<12} {status}"
        )
        print(f"Diarization cache: {diarization_cache_dir()}")
        print("No model weights are bundled or downloaded automatically.")
        return 0
    if args.models_command == "download":
        spec = MODELS[args.model]
        print(f"Downloading {spec.name} from {spec.repository} ({spec.approximate_size}).")
        print("This command requires Internet access. Meeting media is never uploaded.")
        path = download_model(args.model)
        print(f"Model ready: {path}")
        return 0
    if args.models_command == "download-alignment":
        spec = ALIGNMENT_MODELS[args.language]
        print(
            f"Downloading alignment model for {args.language} from {spec.repository} "
            f"({spec.approximate_size}, {spec.license})."
        )
        print("This command requires Internet access. Meeting media is never uploaded.")
        path = download_alignment_model(args.language)
        print(f"Alignment model ready: {path}")
        return 0
    if args.models_command == "download-diarization":
        print(
            f"Acquiring {COMMUNITY_1.repository} ({COMMUNITY_1.approximate_size}, "
            f"{COMMUNITY_1.license}, gated)."
        )
        print("This requires accepted Hugging Face conditions and HF_TOKEN in the environment.")
        print("Model assets are downloaded explicitly; meeting media is never uploaded.")
        path = download_diarization_model()
        print(f"Diarization model ready for offline use: {path}")
        return 0
    return 2


def handle_speakers(args: argparse.Namespace) -> int:
    if args.speakers_command == "list":
        print("No local speaker database has been initialized.")
        return 0
    return 2


def handle_review(args: argparse.Namespace) -> int:
    session = ReviewSession.open(args.output)
    if session.migrated:
        print("Schema v4 loaded as a v5 migration preview; stable IDs persist only when saved.")
    command = args.review_command
    if command == "list":
        segments = session.list_segments(unknown_only=args.unknown_only)
        for segment in segments:
            print(format_segment(session, segment.id))
            print()
        if not segments:
            print("No matching active segments.")
        return 0
    if command == "show":
        print(format_segment(session, args.reference))
        return 0
    if command == "speakers":
        print(format_speakers(session))
        return 0
    if command == "assign-speaker":
        session.assign_cluster(args.cluster, args.name)
    elif command == "assign-segment":
        session.assign_segment(args.reference, display_name=args.name, cluster=args.cluster)
    elif command == "assign-unknown":
        session.assign_unknown(args.reference, display_name=args.name, cluster=args.cluster)
    elif command == "merge":
        session.merge(
            args.first,
            args.second,
            display_name=args.name,
            cluster=args.cluster,
        )
    elif command == "delete":
        session.delete(args.reference)
    elif command == "interactive":
        run_interactive(session, unknown_only=args.unknown_only)
        return 0
    else:
        return 2
    session.save()
    print("Review saved; transcript exports regenerated without ML.")
    return 0


def configure_logging(verbose: bool = False, debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _add_assignment_target(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    targets = parser.add_mutually_exclusive_group(required=required)
    targets.add_argument("--name", help="Explicit display name or existing known identity name.")
    targets.add_argument("--cluster", help="Explicit existing SPEAKER_NN target cluster.")


def normalize_argv(argv: list[str] | None) -> list[str] | None:
    if argv is None or not argv:
        return argv
    commands = {"doctor", "models", "review", "speakers", "transcribe"}
    first = argv[0]
    if first.startswith("-") or first in commands:
        return argv
    return ["transcribe", *argv]
