import os
import re
from urllib.parse import quote

import xbmc
import xbmcvfs


def channel_logo(channel, addon):
    if addon.getSetting('use_picons_server') == 'true':
        return ('http://' + addon.getSetting('picons_server_ip') + ':'
                + addon.getSetting('picons_server_port') + '/picons/' + quote(channel['name']))
    channel_id = str(channel['id'])
    if not re.fullmatch(r'[A-Za-z0-9_-]+', channel_id):
        xbmc.log('Antik TV > Invalid channel ID for station logo', xbmc.LOGWARNING)
        return None
    addon_path = xbmcvfs.translatePath(addon.getAddonInfo('path'))
    path = os.path.join(addon_path, 'resources', 'stations', 'png', channel_id + '.png')
    return path if os.path.isfile(path) else None
