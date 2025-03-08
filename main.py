# main.py
# Основной файл для запуска управляющего бота (контроллера)

import logging
import os
from dotenv import load_dotenv
from controller.controller_bot import ControllerBot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения из файла .env
load_dotenv()

def main():
    """
    Основная функция для запуска приложения.
    Инициализирует и запускает управляющий бот.
    """
    try:
        logger.info("Запуск управляющего бота...")
        controller_bot = ControllerBot()
        controller_bot.run()
    except Exception as e:
        logger.error(f"Ошибка при запуске приложения: {e}")

if __name__ == "__main__":
    main()