import shutil
import tempfile
from pathlib import Path

from django.test import override_settings
from django.test.runner import DiscoverRunner


class TempMediaTestRunner(DiscoverRunner):
    """Загрузки в тестах уходят во временную папку, а не в рабочие media/ и private/.

    Тестовый клиент ходит по HTTP, поэтому редирект на HTTPS из боевого .env отключается.
    """

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media_dir = Path(tempfile.mkdtemp(prefix="radiotsekh-test-"))
        self._media_override = override_settings(
            MEDIA_ROOT=self._media_dir / "media",
            PRIVATE_MEDIA_ROOT=self._media_dir / "private",
            SECURE_SSL_REDIRECT=False,
        )
        self._media_override.enable()

    def teardown_test_environment(self, **kwargs):
        self._media_override.disable()
        shutil.rmtree(self._media_dir, ignore_errors=True)
        super().teardown_test_environment(**kwargs)
