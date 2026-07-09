#!/usr/bin/env python3
"""Build the openfill companion JAR for solution-finder v1.40.

The original sfinder.jar is not modified.  This script recompiles only
entry.setup.SetupEntryPoint from the v1.40 source with two small rule changes:

1. keep fill pack candidates even when they cannot be built by themselves;
2. when order mode needs sub-solution search, stop after the first valid
   sub-solution for each main solution.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


SOURCE_URL = (
    "https://raw.githubusercontent.com/knewjade/solution-finder/"
    "v1.40/src/main/java/entry/setup/SetupEntryPoint.java"
)
OUTPUT_NAME = "sfinder-openfill-rule.jar"
SOURCE_PATH = Path("entry/setup/SetupEntryPoint.java")


LOCAL_SEARCH_METHOD = """\
    private Stream<? extends List<MinoOperationWithKey>> localSearch(List<MinoOperationWithKey> operationWithKeys, Field field, LinkedList<Piece> pieces, EnumMap<Piece, List<FieldOperationWithKey>> minoEachPieceMap, int maxHeight, ThreadLocal<BuildUpStream> buildUpStreamThreadLocal, Field initField, Piece prev, int prevUsingIndex) {
        Piece piece = pieces.pollFirst();
        try {
            List<FieldOperationWithKey> minos = minoEachPieceMap.get(piece);
            int startIndex = prev == piece ? prevUsingIndex + 1 : 0;

            for (int index = startIndex; index < minos.size(); index++) {
                FieldOperationWithKey fieldOperationWithKey = minos.get(index);
                Field minoField = fieldOperationWithKey.getField();
                if (field.canMerge(minoField)) {
                    LinkedList<MinoOperationWithKey> newOperations = new LinkedList<>(operationWithKeys);
                    newOperations.add(fieldOperationWithKey.getOperation());

                    if (pieces.isEmpty()) {
                        BuildUpStream buildUpStream = buildUpStreamThreadLocal.get();
                        Optional<List<MinoOperationWithKey>> result = buildUpStream.existsValidBuildPattern(initField, newOperations).findFirst();
                        if (result.isPresent()) {
                            return Stream.of(result.get());
                        }
                    } else {
                        Field freeze = field.freeze(maxHeight);
                        freeze.merge(minoField);

                        Optional<? extends List<MinoOperationWithKey>> result = localSearch(newOperations, freeze, pieces, minoEachPieceMap, maxHeight, buildUpStreamThreadLocal, initField, piece, index).findFirst();
                        if (result.isPresent()) {
                            return Stream.of(result.get());
                        }
                    }
                }
            }

            return Stream.empty();
        } finally {
            pieces.addFirst(piece);
        }
    }
"""


def download_source() -> str:
    with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
        return response.read().decode("utf-8")


def patch_source(source: str) -> str:
    source = source.replace(
        "return !sampleOperations.isEmpty();",
        "return true;",
        1,
    )

    source = source.replace(
        ".flatMap(blocks -> localSearch(operationWithKeys, field, blocks, minoEachPieceMap, maxHeight, buildUpStreamThreadLocal, initField, null, 0));",
        ".flatMap(blocks -> localSearch(operationWithKeys, field, blocks, minoEachPieceMap, maxHeight, buildUpStreamThreadLocal, initField, null, 0))\n"
        "                        .limit(1);",
        1,
    )

    start = source.index("    private Stream<? extends List<MinoOperationWithKey>> localSearch(")
    end = source.index("    private SetupFunctions createSetupFunctions", start)
    source = source[:start] + LOCAL_SEARCH_METHOD + source[end:]

    return source


def compile_source(source: str, sfinder_jar: Path, output_jar: Path) -> None:
    javac = shutil.which("javac")
    if javac is None:
        raise RuntimeError("javac was not found on PATH")

    with tempfile.TemporaryDirectory(prefix="sfinder-openfill-") as tmp:
        tmp_path = Path(tmp)
        src_file = tmp_path / "src" / SOURCE_PATH
        classes_dir = tmp_path / "classes"
        src_file.parent.mkdir(parents=True)
        classes_dir.mkdir()
        src_file.write_text(source, encoding="utf-8", newline="\n")

        command = [
            javac,
            "--release",
            "8",
            "-encoding",
            "UTF-8",
            "-cp",
            str(sfinder_jar),
            "-d",
            str(classes_dir),
            str(src_file),
        ]
        subprocess.run(command, check=True)

        output_jar.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_jar, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for class_file in sorted((classes_dir / "entry" / "setup").glob("SetupEntryPoint*.class")):
                target.write(class_file, class_file.relative_to(classes_dir).as_posix())


def build(sfinder_jar: Path, output_jar: Path) -> None:
    source = patch_source(download_source())
    compile_source(source, sfinder_jar, output_jar)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sfinder",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "sfinder.jar",
        help="path to the original sfinder.jar",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / OUTPUT_NAME,
        help="path to write the companion rule JAR",
    )
    args = parser.parse_args()

    if not args.sfinder.exists():
        print(f"sfinder.jar not found: {args.sfinder}", file=sys.stderr)
        return 2

    build(args.sfinder, args.output)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
