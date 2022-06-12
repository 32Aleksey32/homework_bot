import os
import sys
import time
import requests
import telegram
import logging
from dotenv import load_dotenv
from exceptions import ApiErrorException
from http import HTTPStatus


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logger.info('Бот отправляет сообщение в телеграм.', message)
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError(message):
        logger.error('Ошибка отправки сообщения в телеграм.')
    else:
        logger.info('Сообщение в телеграм успешно отправлено.')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту Api-сервиса и возвращает ответ."""
    logger.info('Проверка на запрос к APi-сервису начата.')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code == HTTPStatus.OK:
            return response.json()
        else:
            # logger.error('Эндпоинт не доступен.')
            raise ApiErrorException('Эндпоинт не доступен.')
    except requests.exceptions.RequestException:
        raise ApiErrorException('Ошибка подключения к эндпоинту Api-сервиса.')


def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.info('Проверка ответа от API начата')
    homework_list = response['homeworks']
    if 'homeworks' not in response:
        raise TypeError('В ответе API нет ключа домашнее задание')
    if not isinstance(homework_list, list):
        raise TypeError(
            f'Ответ от API не является списком: response = {response}'
        )
    return homework_list


def parse_status(homework):
    """Извлекает из информации статус домашней работы."""
    logger.info('Проверка статуса домашней работы начата.')
    if 'homework_name' in homework:
        homework_name = homework.get('homework_name')
    else:
        raise KeyError('Отсутствует ключ "homework_name" в ответе от API')
    if 'status' in homework:
        homework_status = homework.get('status')
    else:
        raise KeyError('Отсутствует ключ "status" в ответе от API')
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except KeyError:
        message = ('API вернул неизвестный запрос'
                   f' {homework_status} for {homework_name}'
                   )
        raise ApiErrorException(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    logger.info('Проверка доступа переменных начата.')
    return all((TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN))


def main():
    """Основная логика работы бота."""
    logger.info('Бот запущен')
    if not check_tokens():
        message = (
            'Отсутствуют обязательные переменные окружения: '
            'TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN '
            'Программа принудительно остановлена'
        )
        logger.critical(message)
        sys.exit(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    prev_upd_time = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework_list = check_response(response)
            for homework in homework_list:
                upd_time = homework.get('date_updated')
                if upd_time != prev_upd_time:
                    prev_upd_time = upd_time
                    message = parse_status(homework)
                    send_message(bot, message)
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            time.sleep(RETRY_TIME)
        else:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

    formatter = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')
    handler.setFormatter(formatter)

    main()
