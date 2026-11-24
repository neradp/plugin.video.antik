# -*- coding: utf-8 -*-
import sys
import base64
import threading
import time

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from datetime import datetime
from urllib.parse import urlencode
import json

from resources.lib.session import Session
from resources.lib.api import API
from resources.lib.epg import get_channel_epg
from resources.lib.utils import get_api_url, get_isa_version, get_kodi_version, ua
from resources.lib.channels import Channels
from resources.lib.quality import apply_to_listitem as apply_quality

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

class ArchiveStartPlayer(xbmc.Player):
    def __init__(self, url, epg_duration):
        super().__init__()
        self.url = url
        self.epg_duration = epg_duration
        self.started = threading.Event()

    def onAVStarted(self):
        self.started.set()

    def wait(self):
        monitor = xbmc.Monitor()
        deadline = time.monotonic() + 30
        previous_duration = None
        while time.monotonic() < deadline:
            if self.started.is_set():
                try:
                    if self.getPlayingFile().split('|', 1)[0] != self.url:
                        xbmc.log('Antik TV > Archive start skipped: a different item is playing', xbmc.LOGWARNING)
                        return
                    stream_duration = self.getTotalTime()
                    if stream_duration > 0 and stream_duration == previous_duration:
                        offset = max(0, stream_duration - self.epg_duration)
                        if offset > 0:
                            self.seekTime(offset)
                        xbmc.log('Antik TV > Estimated archive start: {:.1f} seconds'.format(offset), xbmc.LOGINFO)
                        return
                    previous_duration = stream_duration
                except RuntimeError as error:
                    xbmc.log('Antik TV > Archive start seek failed: ' + str(error), xbmc.LOGERROR)
                    return
            if monitor.waitForAbort(0.2):
                return
        xbmc.log('Antik TV > Archive start seek timed out', xbmc.LOGWARNING)

def play_catchup(id, start_ts, end_ts):
    start_ts = int(start_ts)
    end_ts = int(end_ts)
    epg = get_channel_epg(id = id, from_ts = start_ts, to_ts = end_ts)
    if start_ts in epg:
        play_archive(id = epg[start_ts]['channel_id'], start = epg[start_ts]['start'], stop = epg[start_ts]['stop'])
    else:
        play_live(id = id)

def play_live(id):
    isa = get_isa_version()
    kodi = get_kodi_version()
    addon = xbmcaddon.Addon()
    session = Session()
    api = API()
    channels = Channels()
    channels_list = channels.get_channels_list('id')   
    post = {'channel' : id }
    response = api.call_api(api = 'channel/detail', data = post, method = 'post', cookies = session.get_cookies())

    if 'data' in response and 'streams' in response['data'] and len(response['data']['streams']) > 0:
        url = response['data']['streams'][0]['url']
        
        list_item = xbmcgui.ListItem()
        uses_isa = False
        if response['data']['streams'][0]['playlist'] == 'm3u8':
            if 'radio' not in channels_list[id] or channels_list[id]['radio'] == 0:
                list_item.setProperty('inputstream', 'inputstream.adaptive')
                uses_isa = True
                if kodi < 21:
                    list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        else:
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            uses_isa = True
            if kodi < 21:
                list_item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
            list_item.setMimeType('application/dash+xml')
            
        if uses_isa:
            apply_quality(list_item)
            stream_headers = "Referer=https://webtv.tv&User-Agent=" + ua
            list_item.setProperty('inputstream.adaptive.stream_headers', stream_headers)
            if kodi < 21:
                list_item.setProperty('inputstream.adaptive.manifest_headers', stream_headers)

        if 'drm' in response['data']['streams'][0]:
            license_url = 'https://drm.antik.sk/widevine/key'
            drm_headers = urlencode({'Content-Type': 'application/octet-stream', 'User-Agent': ua})
            
            if isa >= 22:
                drm_config = {
                    'com.widevine.alpha': {'license': {'server_url': license_url, 'req_headers': drm_headers}}}
                list_item.setProperty('inputstream.adaptive.drm', json.dumps(drm_config))
            elif isa >= 21.5:
                list_item.setProperty('inputstream.adaptive.drm_legacy', f'com.widevine.alpha|{license_url}|{drm_headers}')
            else:
                list_item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
                list_item.setProperty('inputstream.adaptive.license_key', f'{license_url}||R{{SSM}}|{drm_headers}')

        headers = f"Referer=https://webtv.tv&User-Agent={ua}"
        list_item.setProperty('inputstream.adaptive.stream_headers', headers)
        list_item.setProperty('inputstream.adaptive.manifest_update_parameter', f"|{headers}")
        if kodi >= 21:
            url = f"{url}|{headers}"
        
        list_item.setPath(url)
        list_item.setContentLookup(False)       
        xbmcplugin.setResolvedUrl(_handle, True, list_item)
    else:
        xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300218), xbmcgui.NOTIFICATION_ERROR, 5000)


def play_archive(id, start, stop, download = False, title = 'Antik archive'):
    kodi = get_kodi_version()
    addon = xbmcaddon.Addon()
    session = Session()
    api = API()
    channels = Channels()
    channels_list = channels.get_channels_list('id')   
    post = {'channelIdentifier' : id, 'showStart' : start, 'showStop' : stop}
    response = api.call_api(api = 'archive/verify', data = post, method = 'post', cookies = session.get_cookies())
    if 'showIdentifier' in response and len(response['showIdentifier']) > 0:
        url = get_api_url() + 'archive/playShow/' + response['showIdentifier']
        cookies = '; '.join(f'{name}={value}' for name, value in session.get_cookies().items())
        headers = urlencode({'Cookie': cookies, 'User-Agent': ua, 'Referer': 'https://webtv.tv'})
        if download:
            payload = base64.urlsafe_b64encode(
                json.dumps({'url': url + '|' + headers, 'title': title}, ensure_ascii = False).encode('utf-8')
            ).decode('ascii').rstrip('=')
            xbmc.executebuiltin('RunScript(script.stream.saver,add,{})'.format(payload))
            xbmcplugin.endOfDirectory(_handle, succeeded = True)
            return
        list_item = xbmcgui.ListItem(path = url + '|' + headers)
        if 'radio' not in channels_list[id] or channels_list[id]['radio'] == 0:
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.manifest_headers', headers)
            list_item.setProperty('inputstream.adaptive.stream_headers', headers)
            if kodi < 21:
                list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        start_player = None
        if addon.getSettingBool('archive_start_16'):
            try:
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                stop_time = datetime.fromisoformat(stop.replace('Z', '+00:00'))
                duration = (stop_time - start_time).total_seconds()
                if duration <= 0:
                    raise ValueError('archive end is not after start')
            except (TypeError, ValueError) as error:
                xbmc.log('Antik TV > Cannot determine archive duration: ' + str(error), xbmc.LOGWARNING)
            else:
                start_player = ArchiveStartPlayer(url, duration)
        list_item.setContentLookup(False)       
        xbmcplugin.setResolvedUrl(_handle, True, list_item)
        if start_player:
            start_player.wait()
    else:
        xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300218), xbmcgui.NOTIFICATION_ERROR, 5000)
        if download:
            xbmcplugin.endOfDirectory(_handle, succeeded = False)
