import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from resources.lib.channels import Channels


def find_magick():
    executable = shutil.which('magick')
    if executable:
        return executable
    program_files = os.environ.get('ProgramFiles')
    if program_files:
        executable = os.path.join(program_files, 'ImageMagick', 'magick.exe')
        if os.path.isfile(executable):
            return executable
    return None


def download_svg(url):
    if urlparse(url).scheme != 'https':
        raise ValueError('Logo URL must use HTTPS')
    content = bytearray()
    with requests.get(url, timeout=(5, 25), stream=True) as response:
        response.raise_for_status()
        if urlparse(response.url).scheme != 'https':
            raise ValueError('Logo redirect must use HTTPS')
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content) > 4 * 1024 * 1024:
                raise ValueError('SVG exceeds size limit')
    data = bytes(content)
    if re.search(br'<!\s*(DOCTYPE|ENTITY)', data, re.IGNORECASE):
        raise ValueError('SVG document declarations are not supported')
    root = ET.fromstring(data)
    if root.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('Downloaded logo is not SVG')
    for element in root.iter():
        if element.tag.rsplit('}', 1)[-1] in ('script', 'foreignObject'):
            raise ValueError('Unsupported SVG element')
        for name, value in element.attrib.items():
            if name.rsplit('}', 1)[-1] == 'href' and not value.startswith(('#', 'data:image/png;base64,', 'data:image/jpeg;base64,')):
                raise ValueError('External SVG reference is not supported')
        for value in list(element.attrib.values()) + [element.text or '']:
            for reference in re.findall(r'url\s*\(\s*["\']?([^)"\'\s]+)', value, re.IGNORECASE):
                if not reference.startswith('#'):
                    raise ValueError('External SVG reference is not supported')
    return data


def update_logo(channel, addon_path, executable):
    channel_id = str(channel['id'])
    if not re.fullmatch(r'[A-Za-z0-9_-]+', channel_id):
        raise ValueError('Invalid channel ID')
    url = channel.get('logo')
    if not url:
        raise ValueError('Channel has no logo URL')
    svg = download_svg(url)
    svg_dir = os.path.join(addon_path, 'resources', 'stations', 'svg')
    png_dir = os.path.join(addon_path, 'resources', 'stations', 'png')
    os.makedirs(svg_dir, exist_ok=True)
    os.makedirs(png_dir, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='logo-', dir=png_dir) as work_dir:
        source = os.path.join(work_dir, 'logo.svg')
        target = os.path.join(work_dir, 'logo.png')
        with open(source, 'wb') as file:
            file.write(svg)
        subprocess.run(
            [executable, '-background', 'none', source, '-resize', '256x256',
             '-gravity', 'center', '-extent', '256x256', 'PNG32:' + target],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        with open(target, 'rb') as file:
            if file.read(8) != b'\x89PNG\r\n\x1a\n':
                raise ValueError('ImageMagick did not produce a PNG')
        os.replace(source, os.path.join(svg_dir, channel_id + '.svg'))
        os.replace(target, os.path.join(png_dir, channel_id + '.png'))


def update_station_logos():
    addon = xbmcaddon.Addon()
    executable = find_magick()
    if not executable:
        xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(30055), xbmcgui.NOTIFICATION_ERROR, 10000)
        return
    try:
        channels = list(Channels().get_channels().values())
        if not channels:
            raise ValueError('No channels available')
        addon_path = xbmcvfs.translatePath(addon.getAddonInfo('path'))
        progress = xbmcgui.DialogProgress()
        progress.create('Antik TV', addon.getLocalizedString(30058))
        updated = failed = 0
        cancelled = False
        try:
            for index, channel in enumerate(channels):
                if progress.iscanceled():
                    cancelled = True
                    break
                progress.update(int(index * 100 / len(channels)), channel['name'])
                try:
                    update_logo(channel, addon_path, executable)
                    updated += 1
                except (OSError, ValueError, ET.ParseError, requests.RequestException, subprocess.SubprocessError) as error:
                    failed += 1
                    xbmc.log('Antik TV > Logo update failed for {}: {}'.format(channel.get('id'), error), xbmc.LOGERROR)
        finally:
            progress.close()
        message = addon.getLocalizedString(30057 if cancelled else 30056).format(updated, failed)
        xbmcgui.Dialog().notification('Antik TV', message,
                                      xbmcgui.NOTIFICATION_ERROR if failed else xbmcgui.NOTIFICATION_INFO, 10000)
    except (OSError, ValueError, requests.RequestException) as error:
        xbmc.log('Antik TV > Logo update failed: {}'.format(error), xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Antik TV', addon.getLocalizedString(30059), xbmcgui.NOTIFICATION_ERROR, 10000)
