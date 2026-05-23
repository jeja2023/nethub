import tempfile
import unittest
from pathlib import Path

from panel import docker_entrypoint


class DockerEntrypointTests(unittest.TestCase):
    def test_ensure_file_creates_missing_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "nested" / "config.json"

            docker_entrypoint._ensure_file(str(config))

            self.assertTrue(config.is_file())
            self.assertEqual(config.read_text(encoding="utf-8"), "{}\n")

    def test_ensure_file_leaves_directory_mount_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            docker_entrypoint._ensure_file(td)

            self.assertTrue(Path(td).is_dir())


if __name__ == "__main__":
    unittest.main()
