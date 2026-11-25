# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon

from resources.lib.session import Session
from resources.lib.channels import Channels
from resources.lib.api import API
from resources.lib.utils import get_kodi_version

from datetime import date, datetime, timedelta
import time

def get_live_epg():
    session = Session()
    api = API()
    epg = []
    post = {'type' : 'TV', 'meta' : {'adult' : True, 'promo' : True}}
    response = api.call_api(api = 'channels', method = 'post', data = post, cookies = session.get_cookies())
    if 'epg' in response:
        for channel in response['epg']:
            if 'content' in channel and channel['content'] is not None:
                for item in channel['content']:
                    startts = int(datetime.fromisoformat(item['Start']).timestamp())
                    endts = int(datetime.fromisoformat(item['Stop']).timestamp())
                    if time.time() >= startts and time.time() <= endts:
                        epg.append({'id' : item['SeriesID'], 'title' : item['Title'], 'channel_id' : channel['id'], 'description' : item['Description'], 'startts' : startts, 'endts' : endts, 'start' : item['Start'], 'stop' : item['Stop'], 'genres' : item['Genres']})
        post = {'type' : 'RADIO'}
        response = api.call_api(api = 'channels', method = 'post', data = post, cookies = session.get_cookies())
        if 'epg' in response:
            for channel in response['epg']:
                if 'content' in channel and channel['content'] is not None:
                    for item in channel['content']:
                        startts = int(datetime.fromisoformat(item['Start']).timestamp())
                        endts = int(datetime.fromisoformat(item['Stop']).timestamp())
                        if time.time() >= startts and time.time() <= endts:
                            epg.append({'id' : item['SeriesID'], 'title' : item['Title'], 'channel_id' : channel['id'], 'description' : item['Description'], 'startts' : startts, 'endts' : endts, 'start' : item['Start'], 'stop' : item['Stop'], 'genres' : item['Genres']})
        return epg_api(data = epg, key = 'channel_id')
    else:
        return {}

def get_channel_epg(id, from_ts, to_ts):
    session = Session()
    api = API()
    epg = []
    post = {'date': datetime.fromtimestamp(from_ts).strftime('%Y-%m-%d') ,'offset' : 0, 'limit': 200, 'filter' : [id], 'search' : ''}
    response = api.call_api(api = 'epg/channels', data = post, method = 'post', cookies = session.get_cookies())    
    if not isinstance(response, list):
        xbmc.log('Antik TV > Invalid EPG response for channel ' + str(id), xbmc.LOGWARNING)
        return {}
    if not response:
        return {}
    channel = response[0]
    if not isinstance(channel, dict) or not isinstance(channel.get('epg', []), list):
        xbmc.log('Antik TV > Invalid EPG channel response for channel ' + str(id), xbmc.LOGWARNING)
        return {}
    if 'epg' in channel:
        for item in channel['epg']:
            epg.append(parse_epg_item(item))
        return epg_api(data = epg, key = 'startts')
    else:
        return {}

def parse_epg_item(item):
    startts = int(datetime.fromisoformat(item['Start']).timestamp())
    endts = int(datetime.fromisoformat(item['Stop']).timestamp())
    description = item.get('Description')
    return {'id' : item['SeriesID'], 'title' : item['Title'], 'channel_id' : item['Channel'], 'description' : str(description) if description is not None else '', 'startts' : startts, 'endts' : endts, 'start' : item['Start'], 'stop' : item['Stop'], 'genres' : item['Genres']}

def search_archive_epg(channels, query, now):
    if not channels:
        return []
    archive_days = {channel_id : int(channel.get('archive_days', 14)) for channel_id, channel in channels.items()}
    session = Session()
    api = API()
    cookies = session.get_cookies()
    results = []
    seen = set()
    query = query.casefold()
    for day in range(max(archive_days.values()) + 1):
        epg_date = (date.fromtimestamp(now) - timedelta(days = day)).isoformat()
        channel_ids = [channel_id for channel_id, days in archive_days.items() if days >= day]
        for offset in range(0, len(channel_ids), 50):
            batch = channel_ids[offset:offset + 50]
            post = {'date' : epg_date, 'offset' : 0, 'limit' : 200, 'filter' : batch, 'search' : ''}
            response = api.call_api(api = 'epg/channels', data = post, method = 'post', cookies = cookies)
            if not isinstance(response, list):
                raise ValueError('Invalid archive EPG response')
            for channel in response:
                if not isinstance(channel, dict) or ('epg' in channel and not isinstance(channel['epg'], list)):
                    raise ValueError('Invalid archive EPG channel')
                for item in channel.get('epg', []):
                    title = item.get('Title') if isinstance(item, dict) else None
                    if not isinstance(title, (str, int, float)):
                        xbmc.log('Antik TV > Invalid EPG title in archive search', xbmc.LOGWARNING)
                        continue
                    title = str(title)
                    if query not in title.casefold():
                        continue
                    epg = parse_epg_item(item)
                    epg['title'] = title
                    channel_id = str(epg['channel_id'])
                    key = (channel_id, epg['start'], epg['stop'])
                    if (channel_id in batch and
                            now - max(archive_days[channel_id], 1) * 24 * 60 * 60 < epg['endts'] < now
                            and key not in seen):
                        seen.add(key)
                        results.append(epg)
    return sorted(results, key = lambda item: item['startts'], reverse = True)

def get_channels_epg(channels):
    addon = xbmcaddon.Addon()
    epg_from = int(addon.getSetting('epg_from'))
    epg_to = int(addon.getSetting('epg_to'))
    today_date = datetime.today() 
    today_start_ts = int(time.mktime(datetime(today_date.year, today_date.month, today_date.day) .timetuple()))
    session = Session()
    api = API()
    epg = []
    for day in range(-1*epg_from, epg_to, 1):
        try:
            post = {'date': datetime.fromtimestamp(today_start_ts + (day* 60*60*24)).strftime('%Y-%m-%d') ,'offset' : 0, 'limit': 200, 'filter' : channels, 'search' : ''}
            response = api.call_api(api = 'epg/channels', data = post, method = 'post', cookies = session.get_cookies())    
            for channel in response:
                if 'epg' in channel:
                    for item in channel['epg']:
                        startts = int(datetime.fromisoformat(item['Start']).timestamp())
                        endts = int(datetime.fromisoformat(item['Stop']).timestamp())
                        description = item.get('Description')
                        epg.append({'id' : item['SeriesID'], 'title' : item['Title'], 'channel_id' : item['Channel'], 'description' : str(description) if description is not None else '', 'startts' : startts, 'endts' : endts, 'start' : item['Start'], 'stop' : item['Stop'], 'genres' : item['Genres']})
            time.sleep(1)
        except Exception:
            pass
    return epg

def epg_api(data, key):
    epg = {}
    channels = Channels()
    channels_list = channels.get_channels_list('id', visible_filter = False)            
    for item in data:
        id = item['id']
        channel_id = item['channel_id']
        title = item['title']
        description = item['description']
        startts = item['startts']
        endts = item['endts']
        start = item['start']
        stop = item['stop']
        genres = item['genres']
        epg_item = {'id' : id, 'title' : title, 'channel_id' : channel_id, 'description' : description, 'startts' : startts, 'endts' : endts, 'start' : start, 'stop' : stop, 'genres' : genres}
        if key == 'startts':
            epg.update({startts : epg_item})
        elif key == 'channel_id':
            epg.update({channel_id : epg_item})
        elif key == 'id':
            epg.update({id : epg_item})
        elif key == 'startts_channel_number':
            if channel_id in channels_list:
                epg.update({int(str(startts)+str(channels_list[channel_id]['channel_number']).zfill(5))  : epg_item})
    return epg

def epg_listitem(list_item, epg, logo):
    kodi_version = get_kodi_version()
    genres = []
    if kodi_version >= 20:
        infotag = list_item.getVideoInfoTag()
        infotag.setMediaType('movie')
    else:
        list_item.setInfo('video', {'mediatype' : 'movie'})
    if logo is not None:
        list_item.setArt({'icon' : logo}) 
    if isinstance(epg.get('description'), str) and epg['description']:
        if kodi_version >= 20:
            infotag.setPlot(epg['description'])
        else:
            list_item.setInfo('video', {'plot': epg['description']})
    if 'genres' in epg and epg['genres'] is not None and len(epg['genres']) > 0:
        for genre in epg['genres']:      
          genres.append(genre)
        if kodi_version >= 20:
            infotag.setGenres(genres)
        else:
            list_item.setInfo('video', {'genre' : genres})          
    return list_item

