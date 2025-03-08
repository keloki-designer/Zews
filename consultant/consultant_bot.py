# consultant/consultant_bot.py
# Реализация основного бота-консультанта

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pyrogram import Client
from pyrogram.types import Message
from .openai_integration import OpenAIIntegration
from .google_calendar_integration import GoogleCalendarIntegration

logger = logging.getLogger(__name__)


class ConsultantBot:
    """
    Класс бота-консультанта, который общается с клиентом через Telegram
    и может назначать встречи в Google Meet.
    """

    def __init__(self, phone_number, api_id, api_hash, openai_api_key, consultation_topic):
        """
        Инициализация бота-консультанта.

        Args:
            phone_number (str): Номер телефона клиента для отправки сообщений
            api_id (str): API ID для Telegram
            api_hash (str): API Hash для Telegram
            openai_api_key (str): API ключ для OpenAI
            consultation_topic (str): Тема консультации
        """
        self.phone_number = phone_number
        self.api_id = api_id
        self.api_hash = api_hash
        self.openai_api_key = openai_api_key
        self.consultation_topic = consultation_topic

        # Инициализация клиента Telegram
        self.app = Client(
            "consultant_bot",
            api_id=api_id,
            api_hash=api_hash
        )

        # Инициализация интеграции с OpenAI
        self.openai = OpenAIIntegration(openai_api_key, consultation_topic)

        # Инициализация интеграции с Google Calendar
        self.calendar = GoogleCalendarIntegration()

        # Для отслеживания контекста беседы
        self.conversation_context = {}

        # Флаг для обозначения, что бот работает
        self.is_running = False

        # Функция обратного вызова для логирования
        self.log_callback = None

    def set_log_callback(self, callback):
        """Установка функции обратного вызова для логирования."""
        self.log_callback = callback

    def _log(self, message):
        """Логирование сообщения."""
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    async def send_initial_message(self):
        """Отправка первоначального сообщения клиенту."""
        try:
            # Получение контакта клиента
            contact = await self._get_contact_by_phone(self.phone_number)
            if not contact:
                self._log(f"Контакт с номером {self.phone_number} не найден")
                return False

            # Получение начального сообщения от GPT
            initial_message = await self.openai.get_initial_message()

            # Отправка сообщения клиенту
            await self.app.send_message(contact.id, initial_message)

            self._log(f"Отправлено начальное сообщение клиенту {contact.first_name}")
            return True

        except Exception as e:
            self._log(f"Ошибка при отправке начального сообщения: {e}")
            return False

    async def _get_contact_by_phone(self, phone):
        """Получение контакта по номеру телефона."""
        try:
            # Поиск контакта по номеру телефона
            # Форматируем номер телефона, убирая все нецифровые символы
            formatted_phone = ''.join(filter(str.isdigit, phone))

            # Получаем все контакты из адресной книги
            contacts = await self.app.get_contacts()

            # Ищем контакт с нужным номером телефона
            for contact in contacts:
                contact_phone = ''.join(filter(str.isdigit, contact.phone_number))
                if contact_phone.endswith(formatted_phone[-10:]):
                    return contact

            return None

        except Exception as e:
            self._log(f"Ошибка при поиске контакта: {e}")
            return None

    async def process_message(self, message):
        """
        Обработка входящего сообщения от клиента.

        Args:
            message (Message): Входящее сообщение
        """
        try:
            # Получаем ID пользователя
            user_id = message.from_user.id

            # Если это новый диалог, инициализируем контекст
            if user_id not in self.conversation_context:
                self.conversation_context[user_id] = {
                    "messages": [],
                    "meeting_scheduling": False,
                    "available_slots": []
                }

            context = self.conversation_context[user_id]

            # Добавляем сообщение в контекст
            context["messages"].append({
                "role": "user",
                "content": message.text
            })

            # Если мы находимся в процессе назначения встречи
            if context.get("meeting_scheduling"):
                # Проверяем, выбрал ли клиент временной слот
                selected_slot = self._check_if_slot_selected(message.text, context["available_slots"])

                if selected_slot:
                    # Создаем встречу в Google Calendar
                    meet_link = await self.calendar.create_meeting(
                        self.consultation_topic,
                        selected_slot["start"],
                        selected_slot["end"]
                    )

                    # Отправляем ссылку на встречу
                    response = f"Отлично! Я создал встречу на {selected_slot['start_str']}. "
                    response += f"Вот ссылка для подключения: {meet_link}"

                    await self.app.send_message(user_id, response)

                    # Сбрасываем флаг назначения встречи
                    context["meeting_scheduling"] = False
                    context["available_slots"] = []

                    # Добавляем ответ в контекст
                    context["messages"].append({
                        "role": "assistant",
                        "content": response
                    })

                    return

            # Определяем, есть ли намерение назначить встречу
            meeting_intent = await self.openai.detect_meeting_intent(message.text)

            if meeting_intent and not context.get("meeting_scheduling"):
                # Получаем доступные слоты для встречи на ближайшие 5 дней
                available_slots = await self.calendar.get_available_slots(days=5, duration_minutes=30)

                if available_slots:
                    # Форматируем слоты для отображения
                    slots_text = "\n".join([f"{i + 1}. {slot['start_str']}" for i, slot in enumerate(available_slots)])
                    response = f"Я могу назначить видеовстречу для более детального обсуждения. Вот доступные временные слоты:\n\n{slots_text}\n\nПожалуйста, выберите номер удобного для вас временного слота."

                    # Сохраняем доступные слоты в контексте
                    context["meeting_scheduling"] = True
                    context["available_slots"] = available_slots
                else:
                    response = "К сожалению, на ближайшие дни нет доступных временных слотов для встречи. Могу я помочь вам с чем-то еще?"
            else:
                # Получаем ответ от GPT
                response = await self.openai.get_response(context["messages"])

            # Отправляем ответ
            await self.app.send_message(user_id, response)

            # Добавляем ответ в контекст
            context["messages"].append({
                "role": "assistant",
                "content": response
            })

        except Exception as e:
            self._log(f"Ошибка при обработке сообщения: {e}")
            await self.app.send_message(
                message.from_user.id,
                "Извините, произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте еще раз."
            )

    def _check_if_slot_selected(self, message_text, available_slots):
        """
        Проверяет, выбрал ли клиент временной слот.

        Args:
            message_text (str): Текст сообщения
            available_slots (list): Список доступных слотов

        Returns:
            dict: Выбранный слот или None
        """
        try:
            # Проверяем, содержит ли сообщение номер слота
            for digit in message_text.strip().split():
                if digit.isdigit():
                    slot_index = int(digit) - 1
                    if 0 <= slot_index < len(available_slots):
                        return available_slots[slot_index]

            return None
        except Exception:
            return None

    async def _setup_message_handler(self):
        """Настройка обработчика сообщений."""

        @self.app.on_message()
        async def message_handler(client, message):
            try:
                # Проверяем, является ли сообщение текстовым
                if message.text:
                    # Проверяем, что сообщение от нужного клиента
                    contact = await self._get_contact_by_phone(self.phone_number)
                    if contact and message.from_user.id == contact.id:
                        self._log(f"Получено сообщение от клиента: {message.text[:30]}...")
                        await self.process_message(message)
            except Exception as e:
                self._log(f"Ошибка в обработчике сообщений: {e}")

    async def _start(self):
        """Запуск бота."""
        try:
            # Запуск клиента Telegram
            await self.app.start()

            # Настройка обработчика сообщений
            await self._setup_message_handler()

            # Отправка начального сообщения
            success = await self.send_initial_message()
            if not success:
                self._log("Не удалось отправить начальное сообщение клиенту")
                await self.app.stop()
                return

            self.is_running = True
            self._log("Бот успешно запущен")

            # Ожидаем до остановки бота
            while self.is_running:
                await asyncio.sleep(1)

            # Останавливаем клиент
            await self.app.stop()

        except Exception as e:
            self._log(f"Ошибка при запуске бота: {e}")
            if self.app.is_connected:
                await self.app.stop()

    def run(self):
        """Запуск бота в синхронном контексте."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._start())

    def stop(self):
        """Остановка бота."""
        self.is_running = False
        self._log("Бот остановлен")