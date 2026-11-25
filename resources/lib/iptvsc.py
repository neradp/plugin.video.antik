# -*- coding: utf-8 -*-
import sys
import tempfile

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

from datetime import datetime, timezone
from math import ceil

from resources.lib.channels import Channels
from resources.lib.utils import plugin_id, replace_by_html_entity
from resources.lib.epg import get_channels_epg
from resources.lib.station_logos import channel_logo
from resources.lib.program_artwork import ProgramArtwork

def save_file_test():
    addon = xbmcaddon.Addon()  
    try:
        content = ''
        output_dir = addon.getSetting('output_dir')      
        test_file = output_dir + 'test.fil'
        file = xbmcvfs.File(test_file, 'w')
        file.write(bytearray(('test').encode('utf-8')))
        file.close()
        file = xbmcvfs.File(test_file, 'r')
        content = file.read()
        if len(content) > 0 and content == 'test':
            file.close()
            xbmcvfs.delete(test_file)
            return 1  
        file.close()
        xbmcvfs.delete(test_file)
        return 0
    except Exception:
        file.close()
        xbmcvfs.delete(test_file)
        return 0 

def generate_playlist(output_file = ''):
    addon = xbmcaddon.Addon()
    if addon.getSetting('output_dir') is None or len(addon.getSetting('output_dir')) == 0:
        xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300312), xbmcgui.NOTIFICATION_ERROR, 5000)
        sys.exit() 
             
    channels = Channels()
    channels_list = channels.get_channels_list('channel_number')

    if len(output_file) > 0:
        filename = output_file
    else:
        filename = addon.getSetting('output_dir') + 'playlist.m3u'

    if save_file_test() == 0:
        xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300313), xbmcgui.NOTIFICATION_ERROR, 5000)
        return
    try:
        file = xbmcvfs.File(filename, 'w')
        if file == None:
            xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300313), xbmcgui.NOTIFICATION_ERROR, 5000)
        else:
            file.write(bytearray(('#EXTM3U\n').encode('utf-8')))
            for number in sorted(channels_list.keys()):  
                logo = channel_logo(channels_list[number], addon) or channels_list[number].get('logo') or ''
                if 'archive' not in channels_list[number] or channels_list[number]['archive'] == True:                    
                    if addon.getSetting('catchup_mode') == 'default':
                        line = '#EXTINF:-1 catchup="default" catchup-days="7" catchup-source="plugin://' + plugin_id + '/?action=iptsc_play_stream&id=' + str(channels_list[number]['id']) + '&catchup_start_ts={utc}&catchup_end_ts={utcend}" tvg-chno="' + str(number) + '" tvg-id="' + channels_list[number]['name'] + '" tvh-epg="0" tvg-logo="' + logo + '",' + channels_list[number]['name']
                    else:
                        line = '#EXTINF:-1 catchup="append" catchup-days="7" catchup-source="&catchup_start_ts={utc}&catchup_end_ts={utcend}" tvg-chno="' + str(number) + '" tvg-id="' + channels_list[number]['name'] + '" tvh-epg="0" tvg-logo="' + logo + '",' + channels_list[number]['name']
                else:
                    line = '#EXTINF:-1 tvg-chno="' + str(number) + '" tvg-id="' + channels_list[number]['name'] + '" tvh-epg="0" tvg-logo="' + logo + '",' + channels_list[number]['name']                    
                file.write(bytearray((line + '\n').encode('utf-8')))
                line = 'plugin://' + plugin_id + '/?action=iptsc_play_stream&id=' + str(channels_list[number]['id'])
                if addon.getSetting('isa') == 'true':
                    file.write(bytearray(('#KODIPROP:inputstream=inputstream.ffmpegdirect\n').encode('utf-8')))
                    file.write(bytearray(('#KODIPROP:inputstream.ffmpegdirect.stream_mode=timeshift\n').encode('utf-8')))
                    file.write(bytearray(('#KODIPROP:inputstream.ffmpegdirect.is_realtime_stream=true\n').encode('utf-8')))
                    file.write(bytearray(('#KODIPROP:mimetype=video/mp2t\n').encode('utf-8')))
                file.write(bytearray((line + '\n').encode('utf-8')))
            file.close()
            xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300314), xbmcgui.NOTIFICATION_INFO, 5000)    
    except Exception:
        file.close()
        xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300313), xbmcgui.NOTIFICATION_ERROR, 5000)

def generate_epg(output_file = '', show_progress = True):
    addon = xbmcaddon.Addon()
    channels_ids = []
    channels = Channels()
    if addon.getSetting('all_channels') == 'true':
        filter_channels = False
    else:
        filter_channels = True
    channels_list = channels.get_channels_list('channel_number', visible_filter = filter_channels)
    channels_list_by_id = channels.get_channels_list('id', visible_filter = filter_channels)
    if len(channels_list) > 0:
        if save_file_test() == 0:
            xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300315), xbmcgui.NOTIFICATION_ERROR, 5000)
            return
        output_dir = addon.getSetting('output_dir') 
        dialog = None
        try:
            if len(output_file) > 0:
                filename = output_file
            else:
                filename = output_dir + 'antik_epg.xml'
            monitor = xbmc.Monitor()
            with tempfile.TemporaryFile() as file, ProgramArtwork(addon) as artwork:
                file.write(bytearray(('<?xml version="1.0" encoding="UTF-8"?>\n').encode('utf-8')))
                file.write(bytearray(('<tv generator-info-name="EPG grabber">\n').encode('utf-8')))
                content = ''
                for number in sorted(channels_list.keys()):
                    logo = channel_logo(channels_list[number], addon) or channels_list[number].get('logo') or ''
                    channels_ids.append(channels_list[number]['id'])
                    channel = channels_list[number]['name']
                    content = content + '    <channel id="' + replace_by_html_entity(channel) + '">\n'
                    content = content + '            <display-name lang="cs">' + replace_by_html_entity(channel) + '</display-name>\n'
                    content = content + '            <icon src="' + replace_by_html_entity(logo) + '" />\n'
                    content = content + '    </channel>\n'
                file.write(bytearray((content).encode('utf-8')))
                if show_progress == True:
                    dialog = xbmcgui.DialogProgressBG()
                    dialog.create('Stahování EPG dat')
                for i in range(0, len(channels_ids), 10):
                    cnt = 0
                    content = ''
                    if show_progress == True:
                        dialog.update(int(i/len(channels_ids)*100))
                    epg = get_channels_epg(channels = channels_ids[i:i+10])
                    for epg_item in epg:
                        if monitor.abortRequested():
                            return
                        starttime = datetime.fromtimestamp(epg_item['startts'], timezone.utc).strftime('%Y%m%d%H%M%S')
                        endtime = datetime.fromtimestamp(epg_item['endts'], timezone.utc).strftime('%Y%m%d%H%M%S')
                        content = content + '    <programme start="' + starttime + ' +0000" stop="' + endtime + ' +0000" channel="' + replace_by_html_entity(channels_list_by_id[epg_item['channel_id']]['name']) + '">\n'
                        content = content + '       <title lang="cs">' + replace_by_html_entity(str(epg_item['title'])) + '</title>\n'
                        if epg_item['description'] != None and len(epg_item['description']) > 0:
                            content = content + '       <desc lang="cs">' + replace_by_html_entity(epg_item['description']) + '</desc>\n'
                        if epg_item['genres'] and epg_item['genres'] is not None:
                            for category in epg_item['genres']:
                                content = content + '       <category>' +  replace_by_html_entity(category) + '</category>\n'
                        art = artwork.get(epg_item)
                        image = art.get('fanart') or art.get('poster')
                        if image:
                            content = content + '       <icon src="' + replace_by_html_entity(image) + '" />\n'
                        content = content + '    </programme>\n'
                        cnt = cnt + 1
                        if cnt > 20:
                            file.write(bytearray((content).encode('utf-8')))
                            content = ''
                            cnt = 0
                    file.write(bytearray((content).encode('utf-8')))                          
                file.write(bytearray(('</tv>\n').encode('utf-8')))
                if monitor.abortRequested():
                    return
                file.seek(0)
                output = xbmcvfs.File(filename, 'w')
                if output is None:
                    raise OSError('Unable to open EPG output')
                try:
                    while True:
                        chunk = file.read(65536)
                        if not chunk:
                            break
                        if not output.write(bytearray(chunk)):
                            raise OSError('Unable to write EPG output')
                finally:
                    output.close()
                xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300316), xbmcgui.NOTIFICATION_INFO, 5000)    
        except Exception as error:
            xbmc.log('Antik TV > EPG generation failed: ' + str(error), xbmc.LOGERROR)
            xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300315), xbmcgui.NOTIFICATION_ERROR, 5000)
            sys.exit()
        finally:
            if dialog is not None:
                dialog.close()
    else:
        xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(300317), xbmcgui.NOTIFICATION_ERROR, 5000)
        sys.exit()
