import json
from json import JSONDecodeError
from urllib.parse import urlencode

import re

import os
from requests.exceptions import RequestException
import requests
import pymongo
from hashlib import md5
from config import *
from multiprocessing import Pool

# 生成mongodb数据库对象
client = pymongo.MongoClient(MONGO_URL, connect=False)
db = client[MONGO_DB]

headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/71.0.3578.98 Safari/537.36'
           }


def get_page_index(offset, keyword):
    data = {
        'aid': 24,
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': 20,
        'cur_tab': 3,
        'from': 'gallery',
        'pd': 'synthesis',
    }
    url = 'https://www.toutiao.com/api/search/content/?' + urlencode(data)
    print(url)
    try:
        response = requests.get(url=url, headers=headers)
        if response.status_code == 200:
            response.encoding = 'utf8'  # 原编码不是utf8，会有一定乱码
            return response.text
        return None
    except RequestException as e:
        print(e)
        print("请求json出错")
        return None


def parse_page_index(html):
    try:
        data = json.loads(html)
        # 判断data不为空，且'data'在keys中，并且data['data']不为空
        if data and 'data' in data.keys() and data['data']:
            items = data['data']
            for item in items:
                # 判断abstract为空，且app_info存在，且item['app_info']['db_name']为SITE
                if item and 'abstract' in item.keys() and \
                        item['abstract'] == '' and 'app_info' in item.keys() \
                        and item['app_info']['db_name'] == 'SITE':
                    yield {
                        'title': item['title'],
                        'url': item['article_url']
                    }
    except JSONDecodeError as e:
        print(e)


def get_page_detail(url):
    try:
        response = requests.get(url=url, headers=headers)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException as e:
        print(e)
        print("请求详情页出错")
        return None


def parse_page_detail(html):
    images_pattern = re.compile('gallery: JSON.parse\("(.*?)"\)')
    result = re.search(images_pattern, html)
    if result:
        result_data = re.sub(r'\\', '', result.group(1))
        data = json.loads(result_data)
        images = [sub_image['url'] for sub_image in data['sub_images']]
        for image in images:
            download_image(image)
        return images


def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print("存储到mongodb成功", result)
        return True
    return False


def main(offset):
    html = get_page_index(offset, KEYWORD)
    for item in parse_page_index(html):
        print(item)
        html = get_page_detail(item['url'])
        if html:
            images = parse_page_detail(html)
            save_to_mongo({
                'title': item['title'],
                'url': item['url'],
                'images': images
            })


def download_image(url):
    print("正在下载", url)
    try:
        response = requests.get(url=url, headers=headers)
        if response.status_code == 200:
            save_image(response.content)
        return None
    except RequestException as e:
        print(e)
        print("请求图片出错", url)
        return None


def save_image(content):
    file_path = '{0}/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)


if __name__ == '__main__':
    # main(offset=20)
    groups = [x * 20 for x in range(GROUT_START, GROUP_END + 1)]
    pool = Pool()
    pool.map(main, groups)
