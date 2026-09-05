"""Use normal application settings with a local, inspectable mail sink."""

import os

from crackGreVocab.settings import *  # noqa: F403

EMAIL_FILE_PATH = os.environ["E2E_MAIL_DIR"]
