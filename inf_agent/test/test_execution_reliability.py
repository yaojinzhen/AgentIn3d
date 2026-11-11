"""Regression tests for snapshots, bounded reads and workspace publication."""

import copy
import io
import struct
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from artifact_fixtures import triangle, glb_bytes
from test_core_workflow import TemporaryCase, fake_run
from inf_agent.execution.artifact_validation import (
    ArtifactValidationError,
    validate_glb,
)
from inf_agent.execution.asset_health import inspect_artifact
from inf_agent.execution.service import run_workspace
from inf_agent.workspace.contracts import ContractError, load_json, write_json_atomic
from inf_agent.workspace.manager import create_workspace


class RecordingStream:
    def __init__(self, stream, reads):
        self.stream, self.reads = stream, reads

    def read(self, size=-1):
        self.reads.append(size)
        if size < 0 or size > 1024 * 1024:
            raise AssertionError(f"unbounded/oversized read: {size}")
        return self.stream.read(size)

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        return self.stream.__exit__(*args)

    def __getattr__(self, key):
        return getattr(self.stream, key)


class ExecutionReliabilityTests(TemporaryCase):
    def test_declared_modules_resources_reference_and_design_are_snapshotted(self):
        self.start()
        (self.workspace / "helper.py").write_text("VALUE = 1\n")
        (self.workspace / "textures").mkdir()
        Image.new("RGB", (8, 8), "red").save(self.workspace / "textures/skin.png")
        Image.new("RGB", (8, 8), "blue").save(self.workspace / "reference.png")
        (self.workspace / "design.md").write_text("original design", encoding="utf-8")
        request = load_json(self.workspace / "request.json")
        request.update(
            local_dependencies=["helper.py", "textures"],
            reference_image="reference.png",
        )
        write_json_atomic(self.workspace / "request.json", request)
        with patch("inf_agent.execution.service.run_process", side_effect=fake_run):
            result = run_workspace(self.workspace, render=False)
        run = Path(result["run"])
        config = load_json(run / "input/config.json")
        source = Path(config["source_path"])
        self.assertTrue((source.parent / "helper.py").is_file())
        self.assertTrue((source.parent / "textures/skin.png").is_file())
        reference = Path(config["request"]["reference_image"])
        self.assertTrue(reference.is_relative_to(run / "input"))
        original = reference.read_bytes()
        (self.workspace / "reference.png").write_bytes(b"replaced")
        (self.workspace / "helper.py").write_text("VALUE = 2\n")
        (self.workspace / "design.md").write_text("changed")
        self.assertEqual(reference.read_bytes(), original)
        self.assertEqual((source.parent / "helper.py").read_text(), "VALUE = 1\n")
        self.assertEqual((run / "input/design.md").read_text(), "original design")

    def test_bad_or_missing_dependency_is_rejected_before_allocating_run(self):
        self.start()
        path = self.workspace / "request.json"
        request = load_json(path)
        for value in (
            None,
            "helper.py",
            [123],
            ["missing.py"],
            ["../outside.py"],
            ["runs"],
            ["."],
        ):
            with self.subTest(dependencies=value):
                write_json_atomic(path, {**request, "local_dependencies": value})
                with (
                    self.assertRaises(ContractError),
                    patch(
                        "inf_agent.execution.service.run_process", side_effect=fake_run
                    ),
                ):
                    run_workspace(self.workspace, render=False)
                self.assertFalse((self.workspace / "runs").exists())

    def test_header_inspection_reads_only_twelve_bytes(self):
        path = self.root / "scene.blend"
        path.write_bytes(b"BLENDER-v402" + b"\x00" * 2048)
        with patch.object(Path, "read_bytes", side_effect=AssertionError("full read")):
            self.assertTrue(
                inspect_artifact(path, kind="scene_blend", requested=True)[
                    "header_valid"
                ]
            )

    def test_glb_bin_is_never_read_as_one_payload(self):
        doc, binary = triangle()
        # Padding may contain other resource data; checking geometry must not load it all.
        binary += b"\x00" * (3 * 1024 * 1024)
        doc["buffers"][0]["byteLength"] = len(binary)
        path = self.root / "large.glb"
        path.write_bytes(glb_bytes(doc, binary))
        reads = []
        original = Path.open

        def recording(p, *args, **kwargs):
            stream = original(p, *args, **kwargs)
            return (
                RecordingStream(stream, reads)
                if p == path and args and args[0] == "rb"
                else stream
            )

        with patch.object(Path, "open", new=recording):
            result = validate_glb(path)
        self.assertTrue(result["semantic_valid"])
        self.assertTrue(reads)
        self.assertLessEqual(max(reads), 1024 * 1024)

    def test_failed_json_preparation_never_publishes_workspace(self):
        with patch(
            "inf_agent.workspace.contracts.os.replace",
            side_effect=OSError("injected JSON publication failure"),
        ):
            with self.assertRaises(ContractError):
                create_workspace(self.workspace, prompt="object")
        self.assertFalse(self.workspace.exists())
        self.assertEqual(list(self.root.glob(".asset_create_*")), [])

    def test_publication_io_failure_preserves_complete_staging_and_allows_retry(self):
        with patch(
            "inf_agent.workspace.manager._publish_workspace",
            side_effect=OSError("injected publish failure"),
        ):
            with self.assertRaisesRegex(ContractError, "complete staging preserved"):
                create_workspace(self.workspace, prompt="recoverable prompt")
        self.assertFalse(self.workspace.exists())
        stages = list(self.root.glob(".asset_create_*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual(
            load_json(stages[0] / "request.json")["prompt"].strip(),
            "recoverable prompt",
        )
        self.assertTrue((stages[0] / "asset.py").is_file())
        create_workspace(self.workspace, prompt="retry")
        self.assertTrue((self.workspace / "asset.py").is_file())
        self.assertTrue((stages[0] / "asset.py").is_file())

    def test_preparation_write_failure_never_publishes(self):
        original = Path.write_text

        def fail_asset(path, *args, **kwargs):
            if path.name == "asset.py":
                raise OSError("injected source write failure")
            return original(path, *args, **kwargs)

        with (
            patch.object(Path, "write_text", new=fail_asset),
            self.assertRaises(ContractError),
        ):
            create_workspace(self.workspace, prompt="object")
        self.assertFalse(self.workspace.exists())
        self.assertEqual(list(self.root.glob(".asset_create_*")), [])
        create_workspace(self.workspace, prompt="retry")
        self.assertTrue(self.workspace.is_dir())

    def test_portable_copy_failure_rolls_back_only_owned_files(self):
        from inf_agent.workspace.manager import _publish_by_copy

        original = Path.open
        copies = []

        def fail_second(path, mode="r", *args, **kwargs):
            if mode == "xb" and path.parent == self.workspace:
                copies.append(path)
                if len(copies) == 2:
                    (self.workspace / "user_note.txt").write_text("keep me")
                    raise OSError("injected copy failure")
            return original(path, mode, *args, **kwargs)

        with (
            patch(
                "inf_agent.workspace.manager._publish_workspace",
                side_effect=_publish_by_copy,
            ),
            patch.object(Path, "open", new=fail_second),
        ):
            with self.assertRaisesRegex(ContractError, "complete staging preserved"):
                create_workspace(self.workspace, prompt="original")
        self.assertEqual((self.workspace / "user_note.txt").read_text(), "keep me")
        self.assertEqual([p.name for p in self.workspace.iterdir()], ["user_note.txt"])
        stage = next(self.root.glob(".asset_create_*"))
        self.assertTrue((stage / "asset.py").is_file())
        self.assertTrue((stage / "request.json").is_file())
        with self.assertRaises(ContractError):
            create_workspace(self.workspace, prompt="do not overwrite")
        self.assertEqual((self.workspace / "user_note.txt").read_text(), "keep me")

    def test_portable_interrupt_rolls_back_and_keeps_staging(self):
        from inf_agent.workspace.manager import _publish_by_copy

        with (
            patch(
                "inf_agent.workspace.manager._publish_workspace",
                side_effect=_publish_by_copy,
            ),
            patch(
                "inf_agent.workspace.manager.shutil.copyfileobj",
                side_effect=KeyboardInterrupt,
            ),
        ):
            with self.assertRaises(KeyboardInterrupt) as caught:
                create_workspace(self.workspace, prompt="interrupted")
        self.assertFalse(self.workspace.exists())
        self.assertTrue(
            any(
                "Complete staging preserved" in note
                for note in caught.exception.__notes__
            )
        )
        stage = next(self.root.glob(".asset_create_*"))
        self.assertTrue((stage / "asset.py").is_file())
        create_workspace(self.workspace, prompt="retry after interrupt")

    def test_concurrent_start_has_exactly_one_winner(self):
        import concurrent.futures

        def create(i):
            try:
                create_workspace(self.workspace, prompt=f"prompt {i}")
            except ContractError:
                return False
            return True

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(create, range(8)))
        self.assertEqual(sum(results), 1)
        self.assertTrue((self.workspace / "asset.py").is_file())
        self.assertEqual(list(self.root.glob(".asset_create_*")), [])

    def test_local_import_context_stays_active_and_does_not_change_cwd(self):
        import importlib, sys
        from inf_agent.execution.source_context import asset_source_context

        cwd = Path.cwd()
        initial = list(sys.path)
        for value in (1, 2):
            root = self.root / str(value)
            root.mkdir()
            (root / "snapshot_test_local_helper.py").write_text(f"VALUE = {value}\n")
            with asset_source_context(root):
                helper = importlib.import_module("snapshot_test_local_helper")
                self.assertEqual(helper.VALUE, value)
                self.assertEqual(Path.cwd(), cwd)
            self.assertNotIn("snapshot_test_local_helper", sys.modules)
        self.assertEqual(sys.path, initial)

    def test_chunk_types_json_limits_and_accessor_streams_are_bounded(self):
        from inf_agent.execution.binary_reader import BinaryChunk, BINARY_READ_BYTES

        data = bytes(range(256)) * 1024
        reads = []
        reader = BinaryChunk(RecordingStream(io.BytesIO(data), reads), 0, len(data))
        values = list(reader.values("<B", 0, 4, 20000))
        self.assertEqual([v[0] for v in values[:65]], [data[i * 4] for i in range(65)])
        self.assertLessEqual(max(reads), BINARY_READ_BYTES)
        doc, binary = triangle()
        for component, fmt in [(5121, "B"), (5123, "H"), (5125, "I")]:
            case = copy.deepcopy(doc)
            indices = struct.pack("<3" + fmt, 0, 1, 2)
            payload = binary[:36] + indices
            case["buffers"][0]["byteLength"] = len(payload)
            case["bufferViews"][1]["byteLength"] = len(indices)
            case["accessors"][1]["componentType"] = component
            path = self.root / f"{component}.glb"
            path.write_bytes(glb_bytes(case, payload))
            self.assertTrue(validate_glb(path)["semantic_valid"])
        path = self.root / "reject.glb"
        path.write_bytes(
            struct.pack("<4sII", b"glTF", 2, 24) + struct.pack("<II", 4, 123) + b"data"
        )
        with self.assertRaisesRegex(ArtifactValidationError, "unsupported chunk"):
            validate_glb(path)
        path.write_bytes(glb_bytes(doc, binary))
        with patch("inf_agent.execution.artifact_validation.MAX_GLB_JSON_BYTES", 16):
            with self.assertRaisesRegex(ArtifactValidationError, "JSON chunk exceeds"):
                validate_glb(path)

    def test_traceback_detection_streams_across_block_boundaries(self):
        from inf_agent.execution.asset_health import _log_has_traceback

        path = self.root / "run.log"
        for padding in (0, 65520, 65535, 65536):
            with self.subTest(padding=padding):
                path.write_text(
                    "x" * padding + "\nTraceback (most recent call last):\nboom\n",
                    encoding="utf-8",
                )
                with patch.object(
                    Path, "read_text", side_effect=AssertionError("full log read")
                ):
                    self.assertTrue(_log_has_traceback(path))
        path.write_text("prefix Traceback (most recent call last):\n" + "x" * 200000)
        self.assertFalse(_log_has_traceback(path))

    def test_glb_interleaved_values_cross_read_blocks(self):
        doc, _ = triangle()
        count = 9000
        positions = struct.pack("<4f", 0, 0, 0, 99) * count
        indices = struct.pack("<3I", 0, 1, count - 1)
        doc["buffers"][0]["byteLength"] = len(positions) + len(indices)
        doc["bufferViews"] = [
            dict(buffer=0, byteOffset=0, byteLength=len(positions), byteStride=16),
            dict(buffer=0, byteOffset=len(positions), byteLength=len(indices)),
        ]
        doc["accessors"][0]["count"] = count
        doc["accessors"][1]["componentType"] = 5125
        path = self.root / "interleaved.glb"
        path.write_bytes(glb_bytes(doc, positions + indices))
        self.assertTrue(validate_glb(path)["semantic_valid"])
        corrupt = bytearray(positions)
        struct.pack_into("<f", corrupt, (count - 1) * 16, float("nan"))
        path.write_bytes(glb_bytes(doc, bytes(corrupt) + indices))
        with self.assertRaisesRegex(ArtifactValidationError, "non-finite"):
            validate_glb(path)

    def test_input_image_and_design_failures_never_publish(self):
        image = self.root / "ref.png"
        Image.new("RGB", (8, 8), "blue").save(image)
        original = Path.write_bytes

        def fail_image(path, *args, **kwargs):
            if path.name == "reference.png":
                raise OSError("injected image write failure")
            return original(path, *args, **kwargs)

        with (
            patch.object(Path, "write_bytes", new=fail_image),
            self.assertRaises(ContractError),
        ):
            create_workspace(self.workspace, prompt="object", image=image)
        self.assertFalse(self.workspace.exists())
        self.assertEqual(list(self.root.glob(".asset_create_*")), [])
        self.start()
        (self.workspace / "design.md").mkdir()
        with self.assertRaisesRegex(ContractError, "design.md"):
            run_workspace(self.workspace, render=False)
        self.assertFalse((self.workspace / "runs").exists())

    def test_dependency_directories_preserve_packages_and_ignore_python_cache(self):
        self.start()
        package = self.workspace / "pkg"
        (package / "__pycache__").mkdir(parents=True)
        (package / "__init__.py").write_text("")
        (package / "part.py").write_text("VALUE = 1")
        (package / "__pycache__/part.cpython-311.pyc").write_bytes(b"cache")
        request = load_json(self.workspace / "request.json")
        request["local_dependencies"] = ["pkg", "pkg/part.py", "asset.py"]
        write_json_atomic(self.workspace / "request.json", request)
        with patch("inf_agent.execution.service.run_process", side_effect=fake_run):
            result = run_workspace(self.workspace, render=False)
        config = load_json(Path(result["run"]) / "input/config.json")
        source = Path(config["source_path"]).parent
        self.assertTrue((source / "pkg/__init__.py").is_file())
        self.assertTrue((source / "pkg/part.py").is_file())
        self.assertFalse((source / "pkg/__pycache__").exists())
        self.assertEqual(
            config["input_context"]["files"],
            ["asset.py", "pkg/__init__.py", "pkg/part.py"],
        )

    def test_large_bin_validation_has_bounded_python_peak_memory(self):
        import json, time, tracemalloc

        measurements = []
        for mib in (8, 32):
            doc, binary = triangle()
            length = mib * 1024 * 1024
            doc["buffers"][0]["byteLength"] = length
            text = json.dumps(doc).encode()
            text += b" " * (-len(text) % 4)
            total = 28 + len(text) + length
            path = self.root / f"{mib}_mib.glb"
            with path.open("wb") as stream:
                stream.write(struct.pack("<4sII", b"glTF", 2, total))
                stream.write(struct.pack("<II", len(text), 0x4E4F534A))
                stream.write(text)
                stream.write(struct.pack("<II", length, 0x004E4942))
                stream.write(binary)
                stream.truncate(total)
            tracemalloc.start()
            start = time.perf_counter()
            try:
                self.assertTrue(validate_glb(path)["semantic_valid"])
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            elapsed = time.perf_counter() - start
            measurements.append(
                dict(bin_mib=mib, peak_bytes=peak, seconds=round(elapsed, 4))
            )
            self.assertLess(peak, 6 * 1024 * 1024)
        self.assertLess(
            abs(measurements[1]["peak_bytes"] - measurements[0]["peak_bytes"]),
            2 * 1024 * 1024,
        )
        print("artifact_stream_memory=" + json.dumps(measurements), flush=True)
