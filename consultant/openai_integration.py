# consultant/openai_integration.py
# Интеграция с OpenAI (GPT) для генерации ответов

import logging
import openai

logger = logging.getLogger(__name__)


class OpenAIIntegration:
    """
    Класс для интеграции с OpenAI API и работы с GPT для генерации ответов.
    """

    def __init__(self, api_key, consultation_topic):
        """
        Инициализация интеграции с OpenAI.

        Args:
            api_key (str): API ключ для OpenAI
            consultation_topic (str): Тема консультации
        """
        self.api_key = api_key
        self.consultation_topic = consultation_topic
        self.client = openai.AsyncOpenAI(api_key=api_key)

        # Создаем системный промпт
        self.system_prompt = f"""Ты - профессиональный консультант по {consultation_topic}. 
        Твоя задача - ответить на вопросы клиента, предоставить ценную информацию и в подходящий 
        момент предложить назначить видеовстречу для более детального обсуждения. 
        Не предлагай встречу слишком рано, сначала убедись, что клиент действительно заинтересован. 
        Когда клиент согласится на встречу, спроси о его предпочтениях по времени, а затем предложи 
        конкретные доступные варианты. Общайся естественно, как человек, избегай шаблонных фраз и 
        формулировок, типичных для ботов."""

    async def get_initial_message(self):
        """
        Генерация начального сообщения для клиента.

        Returns:
            str: Начальное сообщение
        """
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user",
                 "content": f"Напиши привлекательное первое сообщение для потенциального клиента, который интересуется {self.consultation_topic}. Не предлагай встречу, просто заинтересуй его."}
            ]

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Ошибка при генерации начального сообщения: {e}")
            return f"Здравствуйте! Я эксперт по {self.consultation_topic}. Чем я могу вам помочь сегодня?"

    async def get_response(self, messages):
        """
        Получение ответа от GPT на сообщение клиента.

        Args:
            messages (list): История сообщений

        Returns:
            str: Ответ GPT
        """
        try:
            # Формируем запрос для GPT
            formatted_messages = [{"role": "system", "content": self.system_prompt}]
            formatted_messages.extend(messages)

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=formatted_messages,
                max_tokens=500,
                temperature=0.7
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Ошибка при получении ответа от GPT: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз."

    async def detect_meeting_intent(self, message):
        """
        Определение намерения клиента назначить встречу.

        Args:
            message (str): Сообщение клиента

        Returns:
            bool: True, если клиент хочет назначить встречу, иначе False
        """
        try:
            # Формируем запрос для определения намерения
            messages = [
                {"role": "system",
                 "content": "Ты - система определения намерений. Определи, хочет ли клиент назначить встречу или видеоконсультацию. Ответь только 'да' или 'нет'."},
                {"role": "user", "content": message}
            ]

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=10,
                temperature=0.1
            )

            intent_response = response.choices[0].message.content.strip().lower()
            return "да" in intent_response

        except Exception as e:
            logger.error(f"Ошибка при определении намерения: {e}")
            return False