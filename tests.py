import pytest
import os
from dotenv import load_dotenv

load_dotenv()  # читает .env и кладёт значения в переменные окружения

API_KEY = os.getenv("API_KEY")
WEBHOOK = os.getenv("WEBHOOK_SECRET")
pytestmark = pytest.mark.anyio


#------------------ test №1 Проверка суммы со скидкой и без --------------

async def test1():
    
