"""Myarra parsing functions. Pure, no I/O, unit-testable."""
import re

KNOWN_STATIONS = ['Filler', 'Seamer', 'Labeler', 'Packaging', 'Quality',
                  'Conveyor', 'Palletizer', 'Wrapper', 'Capper']
LINE_WORDS = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8}
NUMBER_WORDS = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,
                'nine':9,'ten':10,'eleven':11,'twelve':12}

# Job number: WO-2026-001, w0-2026-001, 20-2026-001, work order 2026-001,
# order 2026-001. Two capture groups: the four-digit run and the three-digit run.
JOB_RE = re.compile(
    r'(?:(?:[wW][oO0])|(?:work\s+order)|(?:order)|\d{2})[\s-]*(\d{4})[\s-]*(\d{3})',
    re.IGNORECASE)
HOUR_RE = re.compile(r'\bhour\s*(\d+)\b', re.IGNORECASE)
HOUR_WORD_RE = re.compile(
    r'\bhour\s+(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b',
    re.IGNORECASE)
LINE_DIGIT_RE = re.compile(r'\bline\s*(\d+)\b', re.IGNORECASE)
LINE_WORD_RE = re.compile(
    r'\bline\s+(one|two|three|four|five|six|seven|eight)\b', re.IGNORECASE)
BOTTLES_RE = re.compile(
    r'(\d[\d, ]*\d|\d)\s*(?:bottles?|btl|units?|containers?|cans?|jars?|cases?)\b',
    re.IGNORECASE)
DOWNTIME_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:min|minutes?)\s+(?:of\s+)?(?:downtime|down)\s+(?:at|on)?\s*(?:the\s+)?(.+?)(?:,|$)',
    re.IGNORECASE)


def _strip_job_and_hour(text):
    """Remove job number and hour tokens so bottle counting cannot bleed into them."""
    return HOUR_RE.sub(' ', JOB_RE.sub(' ', text))


def parse_job_number(text):
    m = JOB_RE.search(text)
    if not m:
        return None
    return f"WO-{m.group(1)}-{m.group(2)}"


def parse_all_job_numbers(text):
    """Return every job number in the text, in order."""
    return [f"WO-{m.group(1)}-{m.group(2)}" for m in JOB_RE.finditer(text)]


def parse_hour(text):
    m = HOUR_RE.search(text)
    if m: return int(m.group(1))
    m = HOUR_WORD_RE.search(text)
    if m: return NUMBER_WORDS[m.group(1).lower()]
    return None


def parse_line_number(text):
    m = LINE_DIGIT_RE.search(text)
    if m: return int(m.group(1))
    m = LINE_WORD_RE.search(text)
    return LINE_WORDS.get(m.group(1).lower()) if m else None


def parse_bottles(text):
    clean = _strip_job_and_hour(text)
    m = BOTTLES_RE.search(clean)
    if not m: return None
    return int(re.sub(r'[ ,]', '', m.group(1)))


def parse_downtime(text):
    m = DOWNTIME_RE.search(text)
    if not m: return []
    mins = float(m.group(1))
    rest = m.group(2).strip().rstrip('.,;')
    station = 'unspecified'
    reason = rest
    for s in KNOWN_STATIONS:
        m2 = re.search(rf'\b{re.escape(s)}\b', rest, re.IGNORECASE)
        if m2:
            station = s
            reason = (rest[:m2.start()] + rest[m2.end():]).strip(' ,')
            reason = re.sub(r'\b(?:at|on|the|a|an|of)\b', '', reason, flags=re.IGNORECASE)
            reason = re.sub(r'\s+', ' ', reason).strip()
            break
    return [{'minutes': mins, 'station': station, 'reason': reason or 'unspecified'}]


def parse_int(text):
    m = re.search(r'(\d[\d ,]*\d|\d)', text)
    if not m: return None
    return int(re.sub(r'[ ,]', '', m.group(1)))


def parse_float(text):
    m = re.search(r'(\d+(?:[.,]\d+)?)', text)
    if not m: return None
    return float(m.group(1).replace(',', '.'))
