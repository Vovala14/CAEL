"""Read public article paragraphs as data; ignore media, scripts and references."""
from html.parser import HTMLParser
import re
from .source_quality import intact_text


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
        self.paragraph_lost_math = False
        self.item_lost_math = False
        self.omitted_math_blocks = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '')
        inherited_skip = self.stack[-1][1] if self.stack else False
        omitted_math = tag == 'math' or bool(re.search(r'\b(?:mwe-math|mw-math)[\w-]*\b', classes))
        if omitted_math and not inherited_skip:
            if self.paragraph is not None:
                self.paragraph_lost_math = True
            if self.item is not None:
                self.item_lost_math = True
        skip = inherited_skip or omitted_math or tag in self.SKIP or bool(re.search(
            r'\b(?:mw-editsection|reference|reflist|navbox|sidebar|metadata|thumb|hatnote|shortdescription)\b', classes))
        if tag not in self.VOID:
            self.stack.append((tag, skip))
        if skip:
            return
        if tag in ('h2', 'h3', 'h4'):
            self.heading_buffer = []
        elif tag == 'p':
            self.paragraph = []
            self.paragraph_lost_math = False
        elif tag == 'li' and self.paragraph is None and self.item is None:
            self.item = []
            self.item_lost_math = False

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
            if self.item_lost_math:
                self.omitted_math_blocks += 1
                return
            if not intact_text(body) or not intact_text(self.heading):
                return
            if 20 <= len(body) and self.characters <= 48000 and not re.search(r'(?i)^(?:references|notes|external links|bibliography|further reading|see also|contents)', self.heading):
                if not self.sections or self.sections[-1]['heading'] != self.heading:
                    self.sections.append(dict(heading=self.heading, paragraphs=[]))
                self.sections[-1].setdefault('items', []).append(body[:1000])
                self.characters += len(body)
        if tag == 'p' and self.paragraph is not None:
            body = re.sub(r'\s+', ' ', ''.join(self.paragraph)).strip()
            self.paragraph = None
            if self.paragraph_lost_math:
                self.omitted_math_blocks += 1
                return
            if not intact_text(body) or not intact_text(self.heading):
                return
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
