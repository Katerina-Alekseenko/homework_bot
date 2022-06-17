import logging
import os
import time

import requests

import telegram
from http import HTTPStatus

from dotenv import load_dotenv

import exceptions

from settings import ENDPOINTS, TIME_BETWEEN_ORDERS

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRAKTIKUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = TIME_BETWEEN_ORDERS
ENDPOINT = ENDPOINTS
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.INFO,
)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info('Сообщение отправлено')
    except telegram.error.TelegramError:
        logger.error('Сообщение не отправилось')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except exceptions.APIResponseStatusCodeException:
        logger.error('Сбой при запросе к эндпоинту')
    if response.status_code != HTTPStatus.OK:
        msg = 'Сбой при запросе к эндпоинту'
        logger.error(msg)
        raise exceptions.APIResponseStatusCodeException(msg)
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    homeworks_list = response['homeworks']
    if homeworks_list not in response['homeworks']:
        msg = f'Ошибка доступа по ключу homeworks: {KeyError}'
        logger.error(msg)
        raise exceptions.CheckResponseException(msg)
    elif type(response) is not dict:
        msg = 'Ошибка словаря'
        logger.error(msg)
        raise exceptions.CheckResponseException(msg)
    elif homeworks_list is None:
        msg = 'В ответе API нет словаря с домашней работой'
        logger.error(msg)
        raise exceptions.CheckResponseException(msg)
    elif len(homeworks_list) == 0:
        msg = 'За последнее время не было домашней работы'
        logger.error(msg)
        raise exceptions.CheckResponseException(msg)
    elif not isinstance(homeworks_list, list):
        msg = 'В ответе API домашки представлены не списком'
        logger.error(msg)
        raise exceptions.CheckResponseException(msg)
    return homeworks_list


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе ее статус."""
    if 'homework_name' not in homework:
        raise KeyError(logger.error('Ошибка доступа \'homework_name\''))
    elif 'status' not in homework:
        raise KeyError(logger.error('Ошибка ключа \'status\''))
    elif homework['status'] not in HOMEWORK_STATUSES:
        raise logger.error('Ошибка статуса')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    logger.info('Получен статус')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message_error = 'Проблема с переменными окружения!'
        logger.critical(message_error)
        raise exceptions.EnvironmentVariablesAreMissing(message_error)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status = None
    error_status = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            message = parse_status(check_response(response))
            if message != status:
                send_message(bot, message)
                status = message
            else:
                logger.info('Обновления статуса нет')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if error_status != str(error):
                error_status = str(error)
                send_message(bot, message)
            logger.error(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
