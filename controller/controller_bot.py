# controller/controller_bot.py
# Реализация управляющего бота (контроллера)

import logging
import os
import tkinter as tk
from tkinter import ttk, scrolledtext
from consultant.consultant_bot import ConsultantBot

logger = logging.getLogger(__name__)


class ControllerBot:
    """
    Класс управляющего бота (контроллера) с графическим интерфейсом для управления
    ботом-консультантом и мониторинга его работы.
    """

    def __init__(self):
        """Инициализация управляющего бота и его интерфейса."""
        self.root = tk.Tk()
        self.root.title("Telegram Consultant Bot Controller")
        self.root.geometry("800x600")

        self.consultant_bot = None
        self.running = False

        self._create_interface()

        logger.info("Контроллер инициализирован")

    def _create_interface(self):
        """Создание графического интерфейса."""
        # Фрейм для ввода конфигурации
        config_frame = ttk.LabelFrame(self.root, text="Конфигурация")
        config_frame.pack(fill="x", padx=10, pady=10)

        # Поле для ввода номера телефона клиента
        ttk.Label(config_frame, text="Номер телефона клиента:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.phone_entry = ttk.Entry(config_frame, width=30)
        self.phone_entry.grid(row=0, column=1, padx=5, pady=5)

        # Поле для ввода API-ключа Telegram
        ttk.Label(config_frame, text="API ID Telegram:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.api_id_entry = ttk.Entry(config_frame, width=30)
        self.api_id_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(config_frame, text="API Hash Telegram:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.api_hash_entry = ttk.Entry(config_frame, width=30)
        self.api_hash_entry.grid(row=2, column=1, padx=5, pady=5)

        # Поле для ввода API-ключа OpenAI
        ttk.Label(config_frame, text="API-ключ OpenAI:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.openai_key_entry = ttk.Entry(config_frame, width=30)
        self.openai_key_entry.grid(row=3, column=1, padx=5, pady=5)

        # Поле для ввода темы консультации
        ttk.Label(config_frame, text="Тема консультации:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.topic_entry = ttk.Entry(config_frame, width=30)
        self.topic_entry.grid(row=4, column=1, padx=5, pady=5)

        # Фрейм для кнопок управления
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", padx=10, pady=5)

        # Кнопки для управления ботом
        self.start_button = ttk.Button(control_frame, text="Запустить бота", command=self._start_bot)
        self.start_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(control_frame, text="Остановить бота", command=self._stop_bot, state="disabled")
        self.stop_button.pack(side="left", padx=5)

        # Фрейм для вывода логов
        log_frame = ttk.LabelFrame(self.root, text="Логи")
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_area = scrolledtext.ScrolledText(log_frame, state="disabled", height=15)
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

        # Статус бота
        self.status_label = ttk.Label(self.root, text="Статус: Бот остановлен", foreground="red")
        self.status_label.pack(pady=10)

    def _log_message(self, message):
        """Добавление сообщения в лог-область интерфейса."""
        self.log_area.configure(state="normal")
        self.log_area.insert(tk.END, f"{message}\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state="disabled")
        logger.info(message)

    def _start_bot(self):
        """Запуск бота-консультанта с указанными параметрами."""
        if self.running:
            self._log_message("Бот уже запущен")
            return

        # Получение введенных параметров
        phone = self.phone_entry.get().strip()
        api_id = self.api_id_entry.get().strip()
        api_hash = self.api_hash_entry.get().strip()
        openai_key = self.openai_key_entry.get().strip()
        topic = self.topic_entry.get().strip()

        # Проверка заполнения полей
        if not all([phone, api_id, api_hash, openai_key, topic]):
            self._log_message("Ошибка: Все поля должны быть заполнены")
            return

        # Установка переменных окружения для бота
        os.environ['TELEGRAM_API_ID'] = api_id
        os.environ['TELEGRAM_API_HASH'] = api_hash
        os.environ['OPENAI_API_KEY'] = openai_key

        try:
            # Инициализация и запуск бота-консультанта
            self.consultant_bot = ConsultantBot(
                phone_number=phone,
                api_id=api_id,
                api_hash=api_hash,
                openai_api_key=openai_key,
                consultation_topic=topic
            )

            # Запуск бота в отдельном потоке
            import threading
            bot_thread = threading.Thread(target=self._run_bot_thread)
            bot_thread.daemon = True
            bot_thread.start()

            self.running = True
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.status_label.configure(text="Статус: Бот запущен", foreground="green")

            self._log_message(f"Бот запущен для клиента с номером {phone}")
            self._log_message(f"Тема консультации: {topic}")

        except Exception as e:
            self._log_message(f"Ошибка при запуске бота: {e}")

    def _run_bot_thread(self):
        """Запуск бота в отдельном потоке."""
        try:
            # Передаем функцию обратного вызова для логирования
            self.consultant_bot.set_log_callback(self._log_message)
            self.consultant_bot.run()
        except Exception as e:
            self._log_message(f"Ошибка в работе бота: {e}")
            self._stop_bot()

    def _stop_bot(self):
        """Остановка бота-консультанта."""
        if not self.running:
            return

        try:
            if self.consultant_bot:
                self.consultant_bot.stop()

            self.running = False
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status_label.configure(text="Статус: Бот остановлен", foreground="red")

            self._log_message("Бот остановлен")

        except Exception as e:
            self._log_message(f"Ошибка при остановке бота: {e}")

    def run(self):
        """Запуск основного цикла интерфейса."""
        self.root.mainloop()