# -*- coding: utf-8 -*-
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import json
    
from datetime import date, datetime, timedelta
import time

from resources.lib.utils import get_url, day_translation, day_translation_short
from resources.lib.channels import Channels 
from resources.lib.epg import get_channel_epg, epg_listitem, search_archive_epg
from resources.lib.program_artwork import ProgramArtwork
from resources.lib.station_logos import channel_logo

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])


def add_download_menu(list_item, epg, addon):
    download_url = get_url(action = 'download_archive', id = epg['channel_id'],
                           start = epg['start'], stop = epg['stop'], title = epg['title'])
    list_item.addContextMenuItems([
        (addon.getLocalizedString(300221), 'RunPlugin({})'.format(download_url))
    ])


def list_archive(label):
    addon = xbmcaddon.Addon()    
    xbmcplugin.setPluginCategory(_handle, label)
    channels = Channels()
    channels_list = channels.get_channels_list('channel_number')
    search_label = addon.getLocalizedString(300113)
    list_item = xbmcgui.ListItem(label = search_label)
    url = get_url(action = 'search_archive', label = label + ' / ' + search_label)
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    for number in sorted(channels_list.keys()):  
        if 'archive' not in channels_list[number] or channels_list[number]['archive'] == True or 'archive_days' not in channels_list[number] or channels_list[number]['archive_days'] != 0:
            if 'archive_days' not in channels_list[number]:
                channels_list[number]['archive_days'] = 7
            list_item = xbmcgui.ListItem(label=channels_list[number]['name'])
            logo = channel_logo(channels_list[number], addon)
            if logo:
                list_item.setArt({'icon' : logo, 'thumb' : logo})
            url = get_url(action='list_archive_days', id = channels_list[number]['id'], days = channels_list[number]['archive_days'], label = label + ' / ' + channels_list[number]['name'])  
            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)


def search_archive(label, query = None):
    addon = xbmcaddon.Addon()
    if query is None:
        keyboard = xbmc.Keyboard('', addon.getLocalizedString(300113))
        keyboard.doModal()
        if not keyboard.isConfirmed():
            xbmcplugin.endOfDirectory(_handle, succeeded = False, cacheToDisc = False)
            return
        query = keyboard.getText()
    query = query.strip()
    if not query:
        xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300220), xbmcgui.NOTIFICATION_ERROR, 5000)
        xbmcplugin.endOfDirectory(_handle, succeeded = False, cacheToDisc = False)
        return
    xbmcplugin.setPluginCategory(_handle, label + ' / ' + query)
    xbmcplugin.setContent(_handle, 'twshows')
    channels_list = Channels().get_channels_list('id')
    channels = {str(channel['id']) : channel for channel in channels_list.values()
                if 'archive' not in channel or channel['archive'] == True
                or 'archive_days' not in channel or channel['archive_days'] != 0}
    try:
        results = search_archive_epg(channels, query, time.time())
    except (ValueError, KeyError, TypeError) as error:
        xbmc.log('Antik TV > Archive search failed: ' + str(error), xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300219), xbmcgui.NOTIFICATION_ERROR, 5000)
        xbmcplugin.endOfDirectory(_handle, succeeded = False, cacheToDisc = False)
        return
    with ProgramArtwork(addon) as artwork:
        for epg in results:
            start = datetime.fromtimestamp(epg['startts'])
            end = datetime.fromtimestamp(epg['endts'])
            channel = channels[str(epg['channel_id'])]
            item_label = (day_translation_short[start.strftime('%w')] + ' ' + start.strftime('%d.%m %H:%M') +
                          ' - ' + end.strftime('%H:%M') + ' | ' + channel['name'] + ' | ' + epg['title'])
            list_item = epg_listitem(xbmcgui.ListItem(label = item_label), epg, None)
            antik_art = artwork.get(epg)
            if antik_art:
                list_item.setArt(antik_art)
            list_item.setProperty('IsPlayable', 'true')
            list_item.setContentLookup(False)
            metadata = {'title' : epg['title'], 'description' : epg.get('description') or '',
                        'genres' : epg.get('genres') or [], 'art' : antik_art or {}}
            url = get_url(action = 'play_archive', id = epg['channel_id'], start = epg['start'],
                          stop = epg['stop'], metadata = json.dumps(metadata, ensure_ascii = False))
            add_download_menu(list_item, epg, addon)
            xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)

def list_archive_days(id, label, days):
    xbmcplugin.setPluginCategory(_handle, label)
    channel = Channels().get_channels_list('id').get(id)
    logo = channel_logo(channel, xbmcaddon.Addon()) if channel else None
    for i in range (int(days) + 1):
        day = date.today() - timedelta(days = i)
        if i == 0:
            den_label = 'Dnes'
            den = 'Dnes'
        elif i == 1:
            den_label = 'Včera'
            den = 'Včera'
        else:
            den_label = day_translation_short[day.strftime('%w')] + ' ' + day.strftime('%d.%m')
            den = day_translation[day.strftime('%w')] + ' ' + day.strftime('%d.%m.%Y')
        list_item = xbmcgui.ListItem(label = den)
        if logo:
            list_item.setArt({'icon' : logo, 'thumb' : logo})
        url = get_url(action='list_program', id = id, day_min = i, label = label + ' / ' + den_label)  
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)

def list_program(id, day_min, label):
    addon = xbmcaddon.Addon()
    label = label.replace(addon.getLocalizedString(300112) + ' /','')
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'twshows')
    today_date = datetime.today() 
    today_start_ts = int(time.mktime(datetime(today_date.year, today_date.month, today_date.day) .timetuple()))
    today_end_ts = today_start_ts + 60*60*24 -1
    if int(day_min) == 0:
        from_ts = today_start_ts - int(day_min)*60*60*24
        to_ts = int(time.mktime(datetime.now().timetuple()))
    else:
        from_ts = today_start_ts - int(day_min)*60*60*24
        to_ts = today_end_ts - int(day_min)*60*60*24
    epg = get_channel_epg(id, from_ts, to_ts)
    with ProgramArtwork(addon) as artwork:
        for key in sorted(epg.keys(), reverse = False):
            if int(epg[key]['endts']) > int(time.mktime(datetime.now().timetuple()))-60*60*24*(int(day_min) + 1) and int(epg[key]['endts']) < int(time.mktime(datetime.now().timetuple())):
                list_item = xbmcgui.ListItem(label = day_translation_short[datetime.fromtimestamp(epg[key]['startts']).strftime('%w')] + ' ' + datetime.fromtimestamp(epg[key]['startts']).strftime('%d.%m %H:%M') + ' - ' + datetime.fromtimestamp(epg[key]['endts']).strftime('%H:%M') + ' | ' + epg[key]['title'])
                list_item = epg_listitem(list_item = list_item, epg = epg[key], logo = None)
                antik_art = artwork.get(epg[key])
                if antik_art:
                    list_item.setArt(antik_art)
                list_item.setProperty('IsPlayable', 'true')
                list_item.setContentLookup(False)
                url = get_url(action='play_archive', id = epg[key]['channel_id'], start = epg[key]['start'], stop = epg[key]['stop'])
                add_download_menu(list_item, epg[key], addon)
                xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)
