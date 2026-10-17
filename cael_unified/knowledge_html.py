"""Read public article paragraphs as data; ignore media, scripts and references."""
from html.parser import HTMLParser
import re


class ArticleText(HTMLParser):
    VOID = {'br', 'hr', 'img', 'meta', 'link', 'input', 'source', 'wbr'}
    SKIP = {'script', 'style', 'table', 'figure', 'sup', 'nav', 'footer', 'math'}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.paragraph = None
        self.heading_buffer = None
        self.heading = 'Introduction'
        self.sections = []
        self.characters = 0
        self.item = None          # list items are kept apart from paragraphs ("items")

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '')
        skip = (self.stack[-1][1] if self.stack else False) or tag in self.SKIP or bool(re.search(
            r'\b(?:mw-editsection|reference|reflist|navbox|sidebar|metadata|thumb|hatnote|shortdescription)\b', classes))
        if tag not in self.VOID:
            self.stack.append((tag, skip))
        if skip:
            return
        if tag in ('h2', 'h3', 'h4'):
            self.heading_buffer = []
        elif tag == 'p':
            self.paragraph = []
        elif tag == 'li' and self.paragraph is None and self.item is None:
            self.item = []

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if tag in ('h2', 'h3', 'h4') and self.heading_buffer is not None:
            self.heading = re.sub(r'\s+', ' ', ''.join(self.heading_buffer)).strip()
            self.heading_buffer = None
        if tag == 'li' and self.item is not None:
            body = re.sub(r'\s+', ' ', ''.join(self.item)).strip()
            self.item = None
            if 20 <= len(body) and self.characters <= 48000 and not re.search(r'(?i)^(?:references|notes|external links|bibliography|further reading|see also|contents)', self.heading):
                if not self.sections or self.sections[-1]['heading'] != self.heading:
                    self.sections.append(dict(heading=self.heading, paragraphs=[]))
                self.sections[-1].setdefault('items', []).append(body[:1000])
                self.characters += len(body)
        if tag == 'p' and self.paragraph is not None:
            body = re.sub(r'\s+', ' ', ''.join(self.paragraph)).strip()
            self.paragraph = None
            if len(body) < 60 or self.characters > 48000 or re.search(r'(?i)^(?:references|notes|external links|bibliography|further reading|see also)', self.heading):
                return
            if not self.sections or self.sections[-1]['heading'] != self.heading:
                self.sections.append(dict(heading=self.heading, paragraphs=[]))
            self.sections[-1]['paragraphs'].append(body[:4000])
            self.characters += len(body)

    def handle_data(self, data):
        if self.stack and self.stack[-1][1]:
            return
        if self.heading_buffer is not None:
            self.heading_buffer.append(data)
        elif self.paragraph is not None:
            self.paragraph.append(data)
        elif self.item is not None:
            self.item.append(data)
