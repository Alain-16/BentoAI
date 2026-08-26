from typing import Annotated
from fastapi import Depends
from bentoai.config import Settings, get_settings


SettingsDeps = Annotated[Settings, Depends(get_settings)]

