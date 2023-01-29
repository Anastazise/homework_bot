import logging
import os
import time
from http import HTTPStatus
import sys
import requests
import telegram
from dotenv import load_dotenv
import json

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s'
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка доступности необходимых токенов."""
    token = all([
        PRACTICUM_TOKEN is not None,
        TELEGRAM_TOKEN is not None,
        TELEGRAM_CHAT_ID is not None
    ])
    return token


def send_message(bot, message):
    """Отправляет сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Отправлено сообщение: "{message}"')
    except Exception as error:
        logging.error(f'Cбой отправки, ошибка: {error}')


def get_api_answer(timestamp):
    """Отправляет запрос к API домашки."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.ConnectionError as connect_error:
        raise logger.error('Ошибка подключения:', connect_error)
    except requests.exceptions.Timeout as timout_error:
        raise logger.error('Время запроса вышло', timout_error)
    except requests.exceptions.RequestException as request_error:
        raise logger.error(request_error)
    if response.status_code != HTTPStatus.OK:
        logger.error('Ошибка. Эндпоинт {ENDPOINT} недоступен.'
            'Код ответа API: {0}'.format(response.status_code)
        )
        raise SystemError()
    try:
        logger.info('Получен JSON-формат')
        return response.json()
    except json.JSONDecodeError():
        raise logger.error('Полученный ответ не в ожидаемом JSON-формате')


def check_response(response):
    """Проверка ответа от ЯндексПрактикума."""
    if type(response) == dict:
        homework = response.get('homeworks')
        if homework is None:
            logging.error('не содержит homeworks')
            raise KeyError('не содержит homeworks')
        if not isinstance(homework, list):
            logging.error('cодержимое не list')
            raise TypeError('cодержимое не list')
    else:
        raise TypeError('Ответ от Домашки не словарь')
    return homework


def parse_status(homework):
    """Получение информации о домашке."""
    keys = ['homework_name', 'status']
    for key in keys:
        if key not in homework:
            message = f'Нет ключа {key}'
            raise KeyError(message)

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)

    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Недопустимый домашней работы'
        raise KeyError(message)

    if homework_name is None:
        logging.error('В ответе API нет ключа homework_name')
        raise KeyError('В ответе API нет ключа homework_name')

    if homework_status is None:
        logging.error('В ответе API нет ключа homework_status')
        raise KeyError('В ответе API нет ключа homework_status')

    if verdict is None:
        logging.error('Неизвестный статус')
        raise KeyError('Неизвестный статус')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens():
        logging.info('Токены впорядке')
    else:
        logging.critical(
            'Не обнаружен один из ключей PRACTICUM_TOKEN,'
            'TELEGRAM_TOKEN, TELEGRAM_CHAT_ID'
        )
        raise SystemExit(
            'Не обнаружен один из ключей PRACTICUM_TOKEN,'
            'TELEGRAM_TOKEN, TELEGRAM_CHAT_ID'
        )
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD

    while True:
        try:
            if type(timestamp) is not int:
                raise SystemError('В функцию передана не дата')
            response = get_api_answer(timestamp)
            response = check_response(response)

            message = parse_status(response[0])
            if message is not None:
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            timestamp = int(time.time())
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
