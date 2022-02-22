import os, base64
import time
from threading import Thread
from typing import Optional, List

import requests
from loguru import logger
from vk_api import VkApi, Captcha
from vk_api.exceptions import VkApiError, ApiError

import config
from db import DB

db = DB()


def write_tokens_file(path: str, tokens: list) -> None:
    file = open(path, 'w')
    file.writelines(tokens)
    logger.debug(f"Saved {len(tokens)} tokens!")


def read_file(path: str) -> List[str]:
    if os.path.exists(path):
        file = open(path, 'r')
        return [i.replace('\n', '') for i in file.readlines()]
    raise Exception("tokens not found") if path == config.tokens_file else Exception("ids file not found")


def validate_tokens(tokens: list, del_invalid_token=False) -> List[str]:
    valid_tkns = []
    counter = 0
    for token in tokens:
        try:
            vk = VkApi(token=token).get_api()
            vk.users.get()
            valid_tkns.append(token)
        except VkApiError as e:
            counter += 1
            logger.debug(f"token - {token} invalid. Invalid tokens - {counter}")
            continue

    if del_invalid_token and tokens != valid_tkns:
        write_tokens_file(config.tokens_file, valid_tkns)

    return valid_tkns


def captcha_handler(captcha: Captcha):
    logger.debug(f"[{captcha.kwargs['values']['bot_id']}]: I get captcha!")
    logger.debug(f'{captcha.url}')

    image = requests.get(captcha.url)
    img64 = base64.encodebytes(image.content)

    send_captcha = requests.post("http://rucaptcha.com/in.php", data=dict(
        key=config.rucaptcha_api_key,
        method='base64',
        body=img64,
        json=True
    )).json()

    if send_captcha.get('status') == 1:
        captcha_key = None
        time.sleep(3)

        while captcha_key is None:
            get_captcha = requests.get(f"http://rucaptcha.com/res.php?key={config.rucaptcha_api_key}&action=get&id={send_captcha['request']}&json=true").json()
            captcha_key = get_captcha.get('request') if get_captcha.get('status') == 1 else None

            time.sleep(5)

        logger.info(f"Капча решена, код капчи: {captcha_key}")
        captcha.try_again(captcha_key)
    captcha.try_again()


def err(val):
    logger.error(f"Error: {val}")


def bot(token: str, ids: List[str]):
    vk = VkApi(token=token, captcha_handler=captcha_handler)
    api = vk.get_api()

    bot_id = api.users.get()[0]
    name = bot_id['first_name'] + ' ' + bot_id['last_name']

    logger.info(f"Bot {name!r} start working")

    for user_id in ids:
        try:
            if user_id not in db.used_ids:
                api.messages.send(user_id=user_id, random_id=0, **config.message, bot_id=bot_id['id'])
                db.used_ids.append(user_id)
                db.save()
                logger.debug(f"Send message to `https://vk.com/id{user_id}`")
            logger.debug(f"User `https://vk.com/id{user_id}` passed")
        except ApiError as e:
            logger.error(f"Error: {e}")

            if e.code in [902, 7]:
                db.used_ids.append(user_id)
                db.save()
            continue


if __name__ == '__main__':
    ids = read_file(config.id_file)
    tokens = validate_tokens(read_file(config.tokens_file), config.delete_invalid_tokens)
    logger.info(f"Loaded `{len(ids)} ids` and `{len(tokens)} tokens`")

    # Запускаю ботов
    for token in tokens:
        th = Thread(target=bot, args=(token, ids,))
        th.start()
