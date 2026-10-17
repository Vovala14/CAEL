"""Accept only explicit commercial-compatible image licences."""
import re


def commercial_image_licence(value):
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(r'(?:CC BY(?:-SA)? [1-4]\.0|CC0(?: 1\.0)?|Public domain|MIT|Apache(?:[- ]2\.0)?)', value.strip(), re.I))


def image_credits(sources):
    lines = []
    for item in sources:
        name, licence = item['source'], item['licence']
        licence_url = item.get('licence_url')
        if not licence_url:
            licence_url = ('https://creativecommons.org/licenses/by-sa/4.0/' if 'BY-SA' in licence else
                           'https://creativecommons.org/licenses/by/4.0/' if 'BY' in licence else
                           'https://creativecommons.org/publicdomain/zero/1.0/' if licence.startswith('CC0') else
                           'https://github.com/microsoft/fluentui-emoji/blob/main/LICENSE' if licence == 'MIT' else '')
        credit = item.get('attribution') or name
        if name.startswith('Emojitwo'):
            credit += '; Emojitwo community, originally EmojiOne 2.2 by Ranks.com; https://github.com/EmojiTwo/emojitwo/; https://www.emojione.com'
        lines.append(f"{credit} — {item['url']} ({licence}; {licence_url})")
    if sources:
        lines.append('Reference shapes normalized and transformed by CAEL. Retain attribution with reused outputs.')
    if any('BY-SA' in item['licence'] for item in sources):
        lines.append('Outputs derived from these share-alike references are distributed under CC BY-SA 4.0.')
    return '\n'.join(lines)
