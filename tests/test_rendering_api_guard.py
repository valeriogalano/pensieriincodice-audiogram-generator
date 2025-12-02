import unittest

from audiogram_generator import cli
from audiogram_generator.rendering import facade as rendering_facade


class TestRenderingApiGuard(unittest.TestCase):
    def test_cli_generate_audiogram_points_to_legacy_wrapper(self):
        # Ensure CLI imports the legacy-compatible wrapper, not the meta-based function
        self.assertIs(cli.generate_audiogram, rendering_facade.generate_audiogram)


if __name__ == "__main__":
    unittest.main()
