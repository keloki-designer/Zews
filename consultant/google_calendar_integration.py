# consultant/google_calendar_integration.py
# Интеграция с Google Calendar для создания и управления встречами

import logging
import os
import datetime
import asyncio
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

logger = logging.getLogger(__name__)


class GoogleCalendarIntegration:
    """
    Класс для интеграции с Google Calendar API.
    Позволяет создавать встречи в Google Meet и управлять доступными временными слотами.
    """

    # Права доступа, которые нужны для работы с календарем
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    def __init__(self):
        """Инициализация интеграции с Google Calendar."""
        self.credentials = None
        self.service = None

    async def _get_credentials(self):
        """
        Получение учетных данных для API Google.
        Использует асинхронную обертку для синхронных операций авторизации.

        Returns:
            Credentials: Учетные данные Google API
        """
        # Превращаем синхронный код в асинхронный с помощью run_in_executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_credentials_sync)

    def _get_credentials_sync(self):
        """
        Синхронное получение учетных данных для API Google.

        Returns:
            Credentials: Учетные данные Google API
        """
        creds = None
        # Проверяем, есть ли сохраненные токены
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        # Если нет действительных учетных данных, получаем новые
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Если нет файла с учетными данными, запускаем процесс авторизации
                if not os.path.exists('credentials.json'):
                    logger.error("Файл credentials.json не найден. Получите его из Google Cloud Console.")
                    return None

                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=0)

            # Сохраняем учетные данные для следующего запуска
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        return creds

    async def _initialize_service(self):
        """
        Инициализация сервиса Google Calendar.

        Returns:
            bool: True, если сервис успешно инициализирован, иначе False
        """
        try:
            if self.service:
                return True

            # Получаем учетные данные
            self.credentials = await self._get_credentials()
            if not self.credentials:
                logger.error("Не удалось получить учетные данные Google")
                return False

            # Инициализируем сервис
            loop = asyncio.get_event_loop()
            self.service = await loop.run_in_executor(
                None,
                lambda: build('calendar', 'v3', credentials=self.credentials)
            )

            return True

        except Exception as e:
            logger.error(f"Ошибка при инициализации сервиса Calendar: {e}")
            return False

    async def get_available_slots(self, days=3, duration_minutes=30):
        """
        Получение доступных временных слотов для встречи.

        Args:
            days (int): Количество дней для поиска доступных слотов
            duration_minutes (int): Продолжительность встречи в минутах

        Returns:
            list: Список доступных временных слотов
        """
        try:
            # Инициализируем сервис
            service_initialized = await self._initialize_service()
            if not service_initialized:
                logger.error("Не удалось инициализировать сервис Calendar")
                return []

            # Получаем текущее время и время окончания периода
            now = datetime.datetime.utcnow()
            end_time = now + datetime.timedelta(days=days)

            # Форматируем время для API
            time_min = now.isoformat() + 'Z'
            time_max = end_time.isoformat() + 'Z'

            # Получаем список событий в календаре для указанного периода
            loop = asyncio.get_event_loop()
            events_result = await loop.run_in_executor(
                None,
                lambda: self.service.events().list(
                    calendarId='primary',
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
            )

            events = events_result.get('items', [])

            # Создаем список доступных слотов
            # Учитываем рабочее время (с 9:00 до 18:00)
            available_slots = []

            current_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = end_time.replace(hour=0, minute=0, second=0, microsecond=0)

            # Словарь для хранения занятых временных интервалов
            busy_times = {}

            # Заполняем словарь занятых временных интервалов
            for event in events:
                start = event['start'].get('dateTime')
                end = event['end'].get('dateTime')

                if start and end:
                    start_dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.datetime.fromisoformat(end.replace('Z', '+00:00'))

                    day_key = start_dt.date().isoformat()

                    if day_key not in busy_times:
                        busy_times[day_key] = []

                    busy_times[day_key].append((start_dt, end_dt))

            # Перебираем дни
            while current_date <= end_date:
                day_key = current_date.date().isoformat()

                # Рабочее время для текущего дня
                # Если текущий день - сегодня, начинаем с текущего времени
                if current_date.date() == now.date():
                    work_start = max(
                        current_date.replace(hour=9, minute=0),
                        now.replace(minute=(now.minute // 30) * 30)  # Округляем до ближайших 30 минут
                    )
                else:
                    work_start = current_date.replace(hour=9, minute=0)

                work_end = current_date.replace(hour=18, minute=0)

                # Получаем занятые интервалы для текущего дня
                day_busy_times = busy_times.get(day_key, [])

                # Сортируем занятые интервалы по времени начала
                day_busy_times.sort(key=lambda x: x[0])

                # Текущее время начала свободного слота
                slot_start = work_start

                # Перебираем занятые интервалы
                for busy_start, busy_end in day_busy_times:
                    # Если есть свободное время до начала занятого интервала
                    if slot_start + datetime.timedelta(minutes=duration_minutes) <= busy_start:
                        # Добавляем свободные слоты с интервалом в 30 минут
                        current_slot = slot_start
                        while current_slot + datetime.timedelta(minutes=duration_minutes) <= busy_start:
                            slot_end = current_slot + datetime.timedelta(minutes=duration_minutes)

                            # Форматируем время для отображения
                            start_str = current_slot.strftime("%d.%m.%Y %H:%M")

                            available_slots.append({
                                "start": current_slot,
                                "end": slot_end,
                                "start_str": start_str
                            })

                            current_slot += datetime.timedelta(minutes=30)

                    # Обновляем время начала следующего свободного слота
                    slot_start = max(slot_start, busy_end)

                # Проверяем, осталось ли свободное время до конца рабочего дня
                if slot_start + datetime.timedelta(minutes=duration_minutes) <= work_end:
                    current_slot = slot_start
                    while current_slot + datetime.timedelta(minutes=duration_minutes) <= work_end:
                        slot_end = current_slot + datetime.timedelta(minutes=duration_minutes)

                        # Форматируем время для отображения
                        start_str = current_slot.strftime("%d.%m.%Y %H:%M")

                        available_slots.append({
                            "start": current_slot,
                            "end": slot_end,
                            "start_str": start_str
                        })

                        current_slot += datetime.timedelta(minutes=30)

                # Переходим к следующему дню
                current_date += datetime.timedelta(days=1)

            # Возвращаем найденные слоты (ограничиваем до 10 первых)
            return available_slots[:10]

        except Exception as e:
            logger.error(f"Ошибка при получении доступных слотов: {e}")
            return []

    async def create_meeting(self, summary, start_time, end_time):
        """
        Создание встречи в Google Calendar с ссылкой на Google Meet.

        Args:
            summary (str): Название встречи
            start_time (datetime): Время начала встречи
            end_time (datetime): Время окончания встречи

        Returns:
            str: Ссылка на встречу в Google Meet или None в случае ошибки
        """
        try:
            # Инициализируем сервис
            service_initialized = await self._initialize_service()
            if not service_initialized:
                logger.error("Не удалось инициализировать сервис Calendar")
                return None

            # Создаем событие в календаре с включенной видеоконференцией
            event = {
                'summary': summary,
                'location': 'Google Meet',
                'description': f'Видеоконсультация по теме: {summary}',
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'conferenceData': {
                    'createRequest': {
                        'requestId': f'meeting-{start_time.timestamp()}'
                    }
                }
            }

            loop = asyncio.get_event_loop()
            event = await loop.run_in_executor(
                None,
                lambda: self.service.events().insert(
                    calendarId='primary',
                    body=event,
                    conferenceDataVersion=1
                ).execute()
            )

            # Получаем ссылку на Google Meet
            conference_data = event.get('conferenceData', {})
            entry_points = conference_data.get('entryPoints', [])

            for entry_point in entry_points:
                if entry_point.get('entryPointType') == 'video':
                    return entry_point.get('uri')

            return None

        except Exception as e:
            logger.error(f"Ошибка при создании встречи: {e}")
            return None