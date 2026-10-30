"""Copied from rag-chatbot-new/src/screen.py (tested there on 61 cases) so this dashboard stays self-contained.
Runs BEFORE any search or model call on the Ask the data page: personal details are declined, and requests for advice, predictions or
return calculations are refused. Questions about what people say are allowed.
"""
import re

I = re.IGNORECASE

PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"(?<!\d)(?:\+?91[\s-]?|0)?[6-9]\d{9}(?!\d)|(?<!\d)(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]\d{5}(?!\d)"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", I),
    "aadhaar": re.compile(r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}(?!\d)"),
    "long_number": re.compile(r"(?<!\d)\d{9,19}(?!\d)"),                     # account, card, folio-like numbers
    "spaced_card": re.compile(r"(?<!\d)(?:\d{4}[\s-]){3}\d{1,4}(?!\d)"),
    "otp": re.compile(r"\b(?:otp|one[- ]time (?:password|pin)|cvv)\b\D{0,15}\d{3,8}\b|\b\d{4,8}\b\s*(?:is\s+)?(?:my\s+)?otp\b", I),
}

ADVICE = [
    r"^\W*should\b", r"\bshould (?:i|we)\b", r"\b(?:i|we) should\b", r"\bshall i\b", r"\bwhat should i\b",
    r"\bwhat do you (?:think|suggest|recommend)\b", r"\bdo you\s+(?:recommend|suggest|think i)\b",
    r"\b(?:recommend|suggest|advise)\s+(?:me|us|a|an|some|the best|any)\b", r"\byour (?:advice|recommendation|opinion)\b",
    r"\b(?:tell|show|give) me\b.{0,40}\b(?:which|what|best)\b", r"\bbest\b.{0,40}\bfor me\b",
    r"\b(?:better|best|right|suitable)\s+for\s+(?:me|us|my)\b", r"\bwhich\s+is\s+better\b.{0,60}\b(?:or|vs|versus)\b",
    r"\bwould you\s+(?:pick|choose|buy|invest|stop|continue|advise|recommend|suggest|go for)\b", r"\bif you were me\b",
    r"\b(?:is|are)\s+(?:it|this|that|now|these|they)\s+(?:a\s+)?(?:good|safe|wise|right|worth)(?:\s+time)?\s+(?:to\s+|for\s+)?(?:buy|invest|sell|start|stop|continue|redeem|exit)",
    r"\b(?:is|are)\s+it\s+(?:wise|good|safe|smart|ok|okay|worth|right|a good idea)\b",
    r"\b(?:would|will)\s+it\s+be\s+(?:smart|wise|good|better|okay|ok|right|a good idea)\b",
    r"\b(?:is|was)\s+(?:now|this|it)\s+(?:the\s+|a\s+)?(?:right|good|best|perfect|safe)\s+time\b",
    r"\b(?:put|invest|park)\s+(?:all|everything|my savings|my money)\b.{0,40}\b(?:in|into)\b",
    r"\b(?:buy|sell|hold|exit|redeem|invest)\s+(?:now|today)\b", r"\bbuy,? sell,? or hold\b",
    r"\b(?:which|what)\s+(?:is|are)?\s*(?:the\s+)?(?:best|top|good)\s+(?:\d+\s+)?(?:mutual\s+)?funds?\b",
    r"\b(?:best|top)\s+(?:\d+\s+)?(?:mutual\s+)?funds?\s+(?:to|for)\b",
    r"^\W*(?:so\s+|ok\s+|hi\s+|hello\s+)?(?:which|what)\s+(?:mutual\s+)?funds?\s+(?:should|to)\b",   # only when it starts the question
    r"\bwhich\s+(?:mutual\s+)?funds?\s+(?:should\s+(?:i|we)|do you)\b",
    r"^\W*(?:so\s+|ok\s+|hi\s+|hello\s+)?which\s+(?:sip|fund|scheme|stock)s?\s+(?:is|are)\s+(?:best|better)\b",   # only when it starts the question
    # Hinglish and Hindi
    r"\b(?:mujhe|mai|main|me|hum)\b.{0,40}\b(?:karna chahiye|karun|karu|kar du|kar dun|rakhun|bechun|bech du|kharidun|kharid lu|lena chahiye|chhod du|lagana chahiye)\b",
    r"\b(?:konsa|kaunsa|kaun sa|kya)\b.{0,30}\b(?:fund|sip|scheme)\b.{0,30}\b(?:lena|lun|loon|kharid|achha|accha|best|sahi|batao|bataiye)\b",
    r"\b(?:sip|fund)\b.{0,40}\b(?:band|bandh|stop|jari|continue|chalu|pause)\b.{0,25}\b(?:kar|rakh)\w*\s*(?:du|dun|karun|chahiye|ya)\b",
    r"\b(?:band|bandh|stop|pause|continue)\s+kar\s*(?:du|dun|doon)\b",
    r"\b(?:redeem|invest|lumpsum|sip|fund)\b.{0,40}\b(?:karun|karu|kar du|rakhun|batao|bataiye)\b",
    r"\bkya\b.{0,40}\b(?:invest|lumpsum|sip|redeem|fund)\b.{0,30}\b(?:sahi|theek|achha|accha)\s+(?:rahega|hoga|hai)\b",
    r"\b(?:kitna|kitne|kitni)\b.{0,25}\b(?:lagana|lagau|lagaun|invest karna|invest karun)\b",
    r"(?:चाहिए|खरीदूं|बेचूं|बंद कर दूं|रखूं|बंद करूं)",
]
PREDICTION = [
    r"\bwill\s+(?:the\s+)?(?:market|markets|nifty|sensex|stock market|funds?|sip|returns?|economy|it|interest rates?|inflation|rupee|gold|portfolio|(?:small|mid|large)\s*caps?)\b.{0,40}\b(?:go|rise|fall|crash|recover|grow|double|up|down|beat|cross|reach|improve|bounce|drop|increase|decrease|help|hurt|outperform|underperform)\b",
    r"\bwhen\s+will\s+(?:the\s+)?(?:market|nifty|sensex)\b", r"\bwhere\s+will\b.{0,40}\b(?:be|end|reach|go|trade)\b",
    r"\b(?:can|could|would|will)\s+you\b.{0,25}\b(?:predict|forecast)\b", r"^\W*(?:please\s+)?(?:predict|forecast)\b",
    r"\b(?:market|nifty|sensex|stock|bitcoin|price|returns?)\s+(?:prediction|forecast)\b",
    r"^\W*(?:is|are|will|would)\s+(?:the\s+)?(?:market|markets|nifty|sensex|economy|rupee)\b.{0,40}\b(?:going|about|set)\s+to\b",
    r"\bhow\s+(?:high|low|much)\b.{0,25}\b(?:can|will|could)\b.{0,40}\b(?:go|grow|rise|fall|reach|become)\b",
    r"\bnext\s+(?:year|month|week|quarter).{0,40}\b(?:market|nifty|sensex|returns?)\b",
    r"\bwill\b.{0,40}\b(?:outperform|underperform|beat the market|do better|perform better)\b",
    # Hinglish
    r"\bmarket\b.{0,20}\b(?:kab|kya)\b.{0,25}\b(?:girega|badhega|recover|upar|neeche|crash)\b",
    r"\b(?:market|nifty|sensex)\s+(?:girega|badhega|upar jayega|neeche jayega)\b",
    r"\bmarket\b.{0,25}\b(?:upar|neeche|up|down)\s+(?:jayega|jaayega|jaega|aayega)\b",
    r"\bkab tak\b.{0,25}\b(?:double|triple|badhega|ho jayega|recover)\b", r"\b(?:girne|badhne|crash hone|recover hone)\s+wala\b",
    r"\bmarket\b.{0,25}\bgir(?:ega|ne wala)\b",
]
RETURNS = [
    r"\b(?:calculate|compute|work out|estimate)\b.{0,40}\b(?:returns?|xirr|cagr|profit|maturity|corpus)\b",
    r"\bhow much\s+(?:money\s+|wealth\s+|corpus\s+)?(?:will|would|can)\s+(?:i|we|my|a|an|₹|rs)\b.{0,80}\b(?:get|make|earn|grow|become|worth|accumulate|have)\b",
    r"\bwhat\s+will\b.{0,40}\b(?:be worth|become|grow to|be in)\b", r"\bworth\s+in\s+\d{4}\b",
    r"\b(?:what|how much)\s+returns?\b.{0,40}\b(?:can|could|will|should)\s+(?:i|we)\b",
    r"\b(?:compare|comparison of|vs|versus)\b.{0,40}\b(?:returns?|performance|xirr|cagr)\b",
    r"\b(?:highest|best|top|better)\s+returns?\b", r"\btop[- ]performing\b", r"\bbest[- ]performing\b",
    r"\b(?:highest|best|top|lowest)\s+(?:xirr|cagr|returning|performer)\b", r"\bwhich\b.{0,40}\b(?:highest|best)\s+(?:xirr|cagr|returns?)\b",
    r"\b(?:rank|list|name|show)\b.{0,40}\b(?:top|best|highest)\b.{0,40}\b(?:funds?|sips?|schemes?)\b",
    r"\bwhich\b.{0,40}\b(?:gave|gives|has given|have given)\b.{0,20}\b(?:more|highest|best)\b",
    r"\bwhat\s+(?:are|is)\s+the\s+(?:returns?|cagr|xirr)\s+(?:of|on|for)\b",
    r"\bkitna\s+(?:return|profit|paisa|paise)\b.{0,25}\b(?:milega|banega|ho jayega|hoga)\b",
    r"\b(?:return|returns|profit)\b.{0,20}\bkitna\s+(?:milega|banega|hoga)\b",
]
_ADVICE_RE = [re.compile(p, I) for p in ADVICE]
_PRED_RE = [re.compile(p, I) for p in PREDICTION]
_RET_RE = [re.compile(p, I) for p in RETURNS]


def screen_pii(question: str):
    """Return the kinds of personal detail found (empty list if none). Never returns the matched values."""
    return sorted(k for k, pat in PII_PATTERNS.items() if pat.search(question))


def screen_advice(question: str):
    """Return 'advice', 'prediction' or 'returns' if the question asks for that, else None."""
    if any(p.search(question) for p in _PRED_RE):
        return "prediction"
    if any(p.search(question) for p in _RET_RE):
        return "returns"
    if any(p.search(question) for p in _ADVICE_RE):
        return "advice"
    return None
