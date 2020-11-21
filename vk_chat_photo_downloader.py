import multiprocessing
import os
import time
from datetime import datetime as dt

import hues
import requests
import vk_api
from pytz import timezone

from settings import VK_USER_TOKEN, TIMEZONE, INTERVAL

TZ = timezone(TIMEZONE)


def get_photos_urls(vk, user_id, directory):
    hues.info("Начинаю поиск фотографий...")
    photos_urls = {}
    start_from = 0
    while True:
        results = vk.messages.getHistoryAttachments(
            peer_id=user_id, media_type="photo", count=200, start_from=start_from
        )
        if results["items"]:
            for attachment in results["items"]:
                photo = attachment["attachment"]["photo"]
                photo_name = (
                    f"{photo['id']}_{photo['owner_id']} "
                    f"{dt.fromtimestamp(photo['date'], TZ).strftime('%d-%m-%y %H:%M')}.jpg"
                )
                # example: 373772945_105918493 07-07-15 02:29
                photo_save_path = f"{directory}/{photo_name}"
                photo_download_url = photo["sizes"][-1]["url"]
                photos_urls.update({photo_save_path: photo_download_url})
            start_from = results["next_from"]
            hues.log(
                f"Получено {len(photos_urls)} фото, следующее смещение: {start_from}"
            )
        else:
            hues.info(f"Найдено {len(photos_urls)} фото.")
            break
        time.sleep(INTERVAL)
    return photos_urls


def _download(photos_urls):
    photo_save_path, photo_download_url = photos_urls
    result = requests.get(photo_download_url, stream=True)
    if result.status_code == 200:
        hues.log(f"Сохраняю {photo_save_path}...")
        with open(photo_save_path, "wb") as f:
            f.write(result.content)


def download_photos(photos_urls):
    hues.info("Начинаю скачивание...")
    workers = multiprocessing.cpu_count() * 2
    pool = multiprocessing.Pool(processes=workers)
    output = pool.map(_download, photos_urls.items())
    return output


def get_peer_id(vk):
    while True:
        peer_id = input(
            "Введите ID (пользователя/беседы/сообщества) для начала загрузки фото: "
        )
        try:
            peer_id = int(peer_id)
        except ValueError:
            hues.error("ID должен быть числом!")
            continue
        # Групповая беседа
        if peer_id > 2000000000:
            hues.info(f"Групповая беседа {peer_id}")
            break
        # Сообщество
        if peer_id < 0:
            hues.info(f"Сообщество {peer_id}")
            break
        # Пользователь
        try:
            results = vk.users.get(user_ids=peer_id)
            hues.info(
                f"Найден пользователь {results[0]['first_name']} {results[0]['last_name']}"
            )
            break
        except vk_api.exceptions.ApiError:
            hues.error("Неверный id (Пример: 105918493)")
    return peer_id


def create_directory(peer_id):
    hues.info("Создаю папку...")
    directory = f"{peer_id} ({dt.now(TZ).strftime('%d-%m-%y %H:%M:%S')})"
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory


def main():
    vk_session = vk_api.VkApi(token=VK_USER_TOKEN)
    vk = vk_session.get_api()

    peer_id = get_peer_id(vk)
    directory = create_directory(peer_id)

    start_time = time.time()
    photos_urls = get_photos_urls(vk, peer_id, directory)
    output = download_photos(photos_urls)
    end_time = time.time()

    hues.success(
        f"--- {len(output)} фотографий скачано за {end_time - start_time} секунд ---"
    )


if __name__ == "__main__":
    main()
