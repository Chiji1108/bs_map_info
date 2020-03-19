import dateutil
from dateutil.parser import parse
from dateutil.tz import tz
from datetime import datetime, timedelta

import requests
import os
import urllib

import requests
from bs4 import BeautifulSoup

import tweepy
import json
import pprint

STARLIST_TOKEN = os.environ.get("STARLIST_TOKEN")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
ACCESS_SECRET = os.environ.get("ACCESS_SECRET")
CONSUMER_KEY = os.environ.get("CONSUMER_KEY")
CONSUMER_SECRET = os.environ.get("CONSUMER_SECRET")

TIMEZONE = tz.gettz('Asia/Tokyo')

auth = tweepy.auth.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth, wait_on_rate_limit=True)
tweet_list = []

GAMEMODES = {
  "Hot Zone": "ホットゾーン",
  "Present Plunder": "プレゼント泥棒",
  "Gem Grab": "エメハン",
  "Showdown": "バトロイ",
  "Duo Showdown": "デュオ",
  "Heist": "強奪",
  "Bounty": "賞金",
  "Brawl Ball": "サッカー",
  "Siege": "制圧",
  "Takedown": "テイクダウン",
  "Lone Star": "孤高",
  "Robo Rumble": "ロボットファイト",
  "Big Game": "ビッグゲーム",
  "Boss Fight": "ボスファイト",
  "Training": "練習モード",
}

def translate_gamemode(string):
  if string in GAMEMODES.keys():
    return GAMEMODES[string]
  else:
    return None

def get_events():
  url = 'https://api.starlist.pro/v1/events'
  headers = {
    'Authorization': f"{STARLIST_TOKEN}"
  }

  r = requests.get(url, headers=headers)
  if r.status_code != 200:
    raise Exception("イベントが取得できてない")
  print(json.dumps(json.loads(r.content),indent=2))
  return r.json()

def get_list(map_id):
  url = f"https://brawlstats.com/events/{map_id}"
  headers = {
    'Accept-Language': 'ja-JP'
  }
  r = requests.get(url,headers=headers)
  soup = BeautifulSoup(r.content, "html.parser")
  names = soup.select("div._1rmYpbetzHMyy6nIIUeAzr div._3lMfMVxY-knKo2dnVHMCWG._21sSMvccqXG6cJU-5FNqzv")
  return list(map(lambda name: name.get_text(strip=True), names))

def remove_all_query(url):
  return urllib.parse.urlunparse(urllib.parse.urlparse(url)._replace(query=None))

def each_slice(arr, n):
  return [arr[i:i + n] for i in range(0, len(arr), n)]

def prepare_tweet(mapped_list, is_first=True):
  temp_time_text = ""
  temp_day_text = ""

  status_list = []
  image_list = []
  for upcoming in mapped_list:
    startTime = parse(upcoming['startTime']).astimezone(TIMEZONE)
    month = str(int(startTime.strftime('%m')))
    day = str(int(startTime.strftime('%d')))
    hour = str(int(startTime.strftime('%H')))
    minute = startTime.strftime('%M')

    nowTime = datetime.now(TIMEZONE)
    today = str(int(nowTime.strftime('%d')))

    day_text = f"{month}/{day}"

    if temp_time_text != f"{day_text} {hour}:{minute}〜":
      temp_time_text = f"{day_text} {hour}:{minute}〜"
      status_list.append("\n")
      if temp_day_text != f"{day_text}":
        temp_day_text = f"{day_text}"
        status_list.append(temp_time_text)
      else:
        status_list.append(f"{hour}:{minute}〜")

    mapId = int(upcoming['mapApiId'])
    map_info = get_list(mapId)
    if map_info[0] == "" or map_info[1] == "":
      map_info[0] = upcoming['gameMode']
      map_info[1] = upcoming['mapName']

    gamemode_prefix = "▼"
    if upcoming['slotName'] == "Power Play":
      gamemode_prefix = "▼PP "
    elif (upcoming['slotName'] == "Ticketed Events"
      or upcoming['slotName'] == "Solo Events"
      or upcoming['slotName'] == "Seasonal Events"
      or upcoming['slotName'] == "Showdown"
      or upcoming['slotName'] == "Daily Events"
      or upcoming['slotName'] == "Team Events"
      or upcoming['slotName'] == "Duo Showdown"
      or upcoming['slotName'] == "Gem Grab"):
      gamemode_prefix = "▼"
    elif is_first == False:
      gamemode_prefix = f"▼{upcoming['slotName']} "

    if translate_gamemode(upcoming['gameMode']) is None:
      status_list.append(f"{gamemode_prefix}{map_info[0]}")
    else:
      status_list.append(f"{gamemode_prefix}{translate_gamemode(upcoming['gameMode'])}")
    status_list.append(f"{map_info[1]}")

    r_image = requests.get(upcoming['mapImageUrl'])
    filename_image = os.path.basename(remove_all_query(upcoming['mapImageUrl']))
    image_list.append('/tmp/' + filename_image)
    with open('/tmp/' + filename_image, 'wb') as f:
      f.write(r_image.content)

  status_list.pop(0)
  status = "\n".join(status_list)

  media_ids = []
  for image in image_list:
    res = api.media_upload(image)
    media_ids.append(res.media_id)

  tweet_list.append([status, media_ids])

def main(event, context):
  # """Triggered from a message on a Cloud Pub/Sub topic.
  # Args:
  #       event (dict): Event payload.
  #       context (google.cloud.functions.Context): Metadata for the event.
  # """
  json_data = get_events()

  upcoming_list = []
  # slotは1,2,3,4だけ取る
  for upcoming in json_data['upcoming']:
    startTime = parse(upcoming['startTime']).astimezone(TIMEZONE)
    if startTime-datetime.now(TIMEZONE) < timedelta(days=1):
      if int(upcoming['slot']) >= 1 and int(upcoming['slot']) <= 4:
        upcoming_list.append([startTime, upcoming])
        continue
  #sort
  sorted_list = sorted(upcoming_list, key=lambda s: s[0])
  mapped_list = list(map(lambda l: l[1], sorted_list))

  prepare_tweet(mapped_list=mapped_list, is_first=True)

  # ---------------- replies

  upcoming_list = []
  # Ticketed Events,PowerPlayなどを取る。5のDUOは含めない
  for upcoming in json_data['upcoming']:
    startTime = parse(upcoming['startTime']).astimezone(TIMEZONE)
    if startTime-datetime.now(TIMEZONE) < timedelta(days=1):
      if int(upcoming['slot']) < 1 or int(upcoming['slot']) > 5:
        upcoming_list.append([startTime, upcoming])
        continue
  #sort
  sorted_list = sorted(upcoming_list, key=lambda s: s[0])
  mapped_list = list(map(lambda l: l[1], sorted_list))

  for m in each_slice(mapped_list, 4):
    prepare_tweet(m, False)

  tweet_id = None
  for tweet in tweet_list:
    if tweet_id is None:
      r = api.update_status(status=tweet[0], media_ids=tweet[1])
    else:
      r = api.update_status(status=tweet[0], media_ids=tweet[1], in_reply_to_status_id=tweet_id, auto_populate_reply_metadata=True)
    tweet_id = r.id

if __name__ == '__main__':
  main(None,None)