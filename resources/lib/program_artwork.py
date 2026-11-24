import os
import sqlite3
from urllib.parse import urlsplit

import xbmc
import xbmcvfs

from resources.lib.api import API
from resources.lib.artwork_cache import ArtworkCache
from resources.lib.session import Session


class ProgramArtwork:
    def __init__(self, addon):
        self.addon = addon
        self.api = None
        self.cookies = None
        self.allow_network = True
        self.cache = None
        self.cache_initialized = False

    def _init_cache(self):
        self.cache_initialized = True
        try:
            profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
            os.makedirs(profile, exist_ok = True)
            self.cache = ArtworkCache(os.path.join(profile, 'antik-artwork-cache.sqlite3'))
        except (OSError, sqlite3.Error) as error:
            xbmc.log('Antik TV > Antik artwork cache unavailable: ' + type(error).__name__, xbmc.LOGWARNING)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.cache is not None:
            self.cache.close()

    def get(self, epg):
        try:
            if not self.cache_initialized:
                self._init_cache()
            return self._get(epg)
        except (ConnectionError, ValueError, TypeError, KeyError) as error:
            xbmc.log('Antik TV > Antik artwork lookup failed: ' + type(error).__name__, xbmc.LOGWARNING)
            if isinstance(error, ConnectionError):
                self.allow_network = False
            return {}

    def _get(self, epg):
        key = ('antik_images', epg['channel_id'], epg['start'], epg['title'])
        if self.cache is not None:
            try:
                found, art = self.cache.get(key)
                if found:
                    return art
            except (sqlite3.Error, ValueError) as error:
                xbmc.log('Antik TV > Artwork cache read failed: ' + type(error).__name__, xbmc.LOGWARNING)
        if not self.allow_network:
            return {}
        if self.api is None:
            self.api = API()
            self.cookies = Session().get_cookies()
        post = {'channel_id' : epg['channel_id'], 'program' : {'start' : epg['start']},
                'includes' : ['images']}
        detail = self.api.call_api(api = 'program/detail', method = 'post', data = post,
                                   cookies = self.cookies, timeout = 10)
        if isinstance(detail, dict) and 'err' in detail:
            raise ConnectionError('Antik program detail request failed')
        if not isinstance(detail, dict) or not isinstance(detail.get('images'), list):
            raise ValueError('Invalid Antik program image response')
        images = {}
        for image in detail['images']:
            if not isinstance(image, dict) or image.get('type') not in ('cover', 'poster'):
                continue
            url = image.get('url')
            try:
                parsed = urlsplit(url) if isinstance(url, str) else None
            except ValueError:
                parsed = None
            if (not parsed or parsed.scheme != 'https' or parsed.netloc != 'extendedepg-gonet.antik.sk'
                    or parsed.query or parsed.fragment):
                xbmc.log('Antik TV > Ignoring invalid program image URL', xbmc.LOGWARNING)
                continue
            images.setdefault(image['type'], url)
        cover = images.get('cover') or images.get('poster')
        art = {'poster' : cover, 'thumb' : cover} if cover else {}
        if images.get('poster'):
            art['fanart'] = images['poster']
        if self.cache is not None:
            try:
                self.cache.put(key, art)
            except sqlite3.Error as error:
                xbmc.log('Antik TV > Artwork cache write failed: ' + type(error).__name__, xbmc.LOGWARNING)
        return art
