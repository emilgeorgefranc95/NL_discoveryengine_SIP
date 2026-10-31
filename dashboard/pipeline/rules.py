"""Analysis rules used by pipeline/export.py. This is the ONE place where the dashboard's definitions live.

Definitions marked DRAFT are the analyst's first read (as the Evidence Log says of the judgement columns) and are meant to be edited here
and re-exported; the dashboard shows them as draft.
"""

# ---- one definition of "tagged" and "relevant", used by every page -------------------------------------------------------------
TAGGED_DEF = "Tagged = an item (post, comment, review) that went through the final (round 2) coding pass and received a label."
RELEVANT_DEF = ("Relevant = a tagged item the engine rated Y (clear) or P (partial): it carries real evidence for at least one of the "
                "nine research questions. Items rated N are tagged but not relevant.")
LAPSE_DEF = ("Lapse story = a relevant item whose author says they stopped, paused or reduced their SIP. People only considering "
             "stopping are not counted.")
LAPSE_OUTCOMES = ("STOPPED", "PAUSED", "REDUCED")
LOW_CONFIDENCE_BELOW = 15          # groups with fewer lapse stories than this are marked low confidence

QUESTIONS = {
    "Q1": "Why do people start a SIP, and what do they expect?",
    "Q2": "What changes in their behaviour in the months after starting?",
    "Q3": "What leads them to pause, reduce or stop?",
    "Q4": "What do they check, and how often?",
    "Q5": "What confuses or worries them?",
    "Q6": "What do they do outside the app when unsure?",
    "Q7": "What separates those who continue from those who drop off?",
    "Q8": "How do patterns differ across segments?",
    "Q9": "What unmet needs come up again and again?",
}
# which theme families answer each question (used for the "top themes" shown under each question)
QUESTION_FAMILIES = {
    "Q1": ("GOAL_", "HABIT_", "TAX_", "PEER_", "FINFLUENCER_", "BANK_OR_", "SMALL_", "FOMO_", "EXP_"),
    "Q2": ("CONT_", "STOP_", "NEED_STEPUP", "PLAT_NO_CONTROL"),
    "Q3": ("STOP_",),
    "Q4": ("CHECK_",),
    "Q5": ("WORRY_",),
    "Q6": ("OUT_",),
    "Q7": ("CONT_", "STOP_"),
    "Q8": (),
    "Q9": ("NEED_", "PLAT_FEATURE", "PLAT_NO_CONTROL"),
}

# ---- metric tree (DRAFT; replace with the Part 2 decomposition) -----------------------------------------------------------------
# Goal: first-time investors who still have an active SIP 12 months after starting.
METRIC_TREE = {
    "B1": "Instalments go through",
    "B2": "Can afford to keep paying, and can adjust",
    "B3": "Believes it is working",
    "B4": "Trusts the platform and gets help",
    "B5": "Has no pull to somewhere else or to forgetting",
}
THEME_BRANCH = {
    "PLAT_MANDATE_FAIL": "B1", "PLAT_EXEC_DELAY": "B1", "STOP_OPS_FAILURE": "B1", "PLAT_FORCED_AUTOPAY": "B1",
    "PLAT_PENALTY_OR_CHARGES": "B1", "PLAT_KYC_BLOCK": "B1",
    "STOP_CASH_CRUNCH": "B2", "STOP_OVERCOMMITTED": "B2", "STOP_JOB_OR_INCOME_LOSS": "B2", "WORRY_CASHFLOW": "B2",
    "PLAT_NO_CONTROL": "B2", "NEED_FLEXIBLE_PAUSE": "B2", "NEED_STEPUP_AUTOMATION": "B2", "NEED_FREQUENCY_OPTIONS": "B2",
    "STOP_MARKET_FALL": "B3", "STOP_UNDERWHELMING_RETURNS": "B3", "WORRY_NEGATIVE_RETURNS": "B3",
    "WORRY_NOT_KNOWING_IF_ON_TRACK": "B3", "EXP_REALITY_GAP": "B3", "NEED_PROGRESS_CLARITY": "B3", "PLAT_DATA_WRONG": "B3",
    "STOP_CONFUSION": "B3", "WORRY_JARGON": "B3", "NEED_PLAIN_LANGUAGE": "B3",
    "STOP_LOST_TRUST": "B4", "PLAT_TRUST_LOSS": "B4", "WORRY_TRUST_PLATFORM": "B4", "PLAT_SUPPORT_FAILURE": "B4",
    "PLAT_WITHDRAW_DELAY": "B4", "NEED_HUMAN_HELP": "B4",
    "STOP_BETTER_ALTERNATIVE": "B5", "STOP_GOAL_REACHED": "B5", "STOP_FAMILY_ADVICE": "B5", "STOP_PASSIVE_DRIFT": "B5",
    "NEED_REMINDER_OR_ALERT": "B5", "WORRY_FUND_CHOICE": "B5",
}

# ---- voluntary vs involuntary (DRAFT) -------------------------------------------------------------------------------------------
# Involuntary: the SIP stops working without the investor choosing it (a debit fails, a block, a platform charge). Voluntary: the
# investor decides. Themes in neither list (support failure, wrong numbers, missing features) describe friction, not a lapse cause.
INVOLUNTARY = {"STOP_OPS_FAILURE", "PLAT_MANDATE_FAIL", "PLAT_EXEC_DELAY", "PLAT_KYC_BLOCK", "PLAT_FORCED_AUTOPAY", "PLAT_PENALTY_OR_CHARGES"}
VOLUNTARY = {"STOP_CASH_CRUNCH", "STOP_OVERCOMMITTED", "STOP_JOB_OR_INCOME_LOSS", "STOP_MARKET_FALL", "STOP_UNDERWHELMING_RETURNS",
             "STOP_BETTER_ALTERNATIVE", "STOP_GOAL_REACHED", "STOP_FAMILY_ADVICE", "STOP_PASSIVE_DRIFT", "STOP_CONFUSION",
             "STOP_LOST_TRUST", "PLAT_TRUST_LOSS", "PLAT_NO_CONTROL"}

# ---- opportunity rows (DRAFT) ---------------------------------------------------------------------------------------------------
# Causes: why the SIP stops or is not kept going. After stopping: what goes wrong when someone exits, redeems or tries to come back.
CAUSE_THEMES = ["STOP_CASH_CRUNCH", "STOP_OVERCOMMITTED", "STOP_JOB_OR_INCOME_LOSS", "STOP_MARKET_FALL", "STOP_UNDERWHELMING_RETURNS",
                "STOP_BETTER_ALTERNATIVE", "STOP_OPS_FAILURE", "PLAT_MANDATE_FAIL", "PLAT_EXEC_DELAY", "PLAT_NO_CONTROL",
                "PLAT_FORCED_AUTOPAY", "STOP_LOST_TRUST", "STOP_CONFUSION", "STOP_PASSIVE_DRIFT", "STOP_GOAL_REACHED", "STOP_FAMILY_ADVICE"]
AFTER_STOP_THEMES = ["PLAT_WITHDRAW_DELAY", "PLAT_PENALTY_OR_CHARGES", "PLAT_KYC_BLOCK", "PLAT_SUPPORT_FAILURE"]

# Fixable within the brief's constraints (no fund or stock recommendations; no fear, FOMO or urgency nudges). Analyst judgement.
FIXABLE = {
    "STOP_CASH_CRUNCH": ("High", "A pause or right-size option answers it without any nudge."),
    "STOP_OVERCOMMITTED": ("High", "A lower amount or step-down is a settings change, not a recommendation."),
    "STOP_JOB_OR_INCOME_LOSS": ("Medium", "Pause and resume help; the cause itself is outside the product."),
    "STOP_MARKET_FALL": ("Low", "Calming a falling market tends to use fear or reassurance framing, which the brief rules out."),
    "STOP_UNDERWHELMING_RETURNS": ("Medium", "Showing progress against the investor's own plan is allowed; promising returns is not."),
    "STOP_BETTER_ALTERNATIVE": ("Low", "Usually a fund or asset choice, which cannot be recommended on."),
    "STOP_OPS_FAILURE": ("High", "Failed debits and retries are product and operations work."),
    "PLAT_MANDATE_FAIL": ("High", "Autopay set-up and retry are in the product's hands."),
    "PLAT_EXEC_DELAY": ("Medium", "Partly the fund house and bank, partly the platform."),
    "PLAT_NO_CONTROL": ("High", "Pause, skip and edit controls are product features."),
    "PLAT_FORCED_AUTOPAY": ("Medium", "A product choice, but linked to mandate rules set outside the platform."),
    "STOP_LOST_TRUST": ("Medium", "Rebuilding trust comes from fixing the failures behind it."),
    "STOP_CONFUSION": ("High", "Plain-language explanations are allowed."),
    "STOP_PASSIVE_DRIFT": ("Medium", "Reminders help, but must not use urgency."),
    "STOP_GOAL_REACHED": ("Low", "A goal reached is a good reason to stop."),
    "STOP_FAMILY_ADVICE": ("Low", "A decision made outside the product."),
    "PLAT_WITHDRAW_DELAY": ("Medium", "Mostly settlement timing set by the fund house, but status visibility is fixable."),
    "PLAT_PENALTY_OR_CHARGES": ("Medium", "Charges come from banks as well as the platform; explaining them is fixable."),
    "PLAT_KYC_BLOCK": ("Medium", "KYC rules are regulatory; the flow around them is fixable."),
    "PLAT_SUPPORT_FAILURE": ("Medium", "An operations and tooling problem."),
}
FIX_WEIGHT = {"High": 1.0, "Medium": 0.6, "Low": 0.25}
SEVERITY_BANDS = ((0.45, "High"), (0.30, "Medium"), (0.0, "Low"))   # DRAFT cut-offs on the share of items (with a stated outcome) whose author actually lapsed
LABEL_OVERRIDES = {"CHECK_XIRR_OR_RETURNS": "XIRR or returns", "PLAT_KYC_BLOCK": "KYC block", "OUT_YOUTUBE_FINFLUENCER": "YouTube or finfluencer",
                   "OUT_REDDIT_FORUM": "Reddit or forums", "STOP_OPS_FAILURE": "Debit or operations failure", "PLAT_MANDATE_FAIL": "Autopay mandate fails",
                   "PLAT_EXEC_DELAY": "Order or debit delay", "WORRY_NOT_KNOWING_IF_ON_TRACK": "Not knowing if on track", "NEED_STEPUP_AUTOMATION": "Step-up automation"}

ITEM_SEVERITY = {"STOPPED": 4, "PAUSED": 3, "REDUCED": 2, "CONSIDERING_STOPPING": 1}   # per-item order used by the explorer

SOURCE_LABEL = {"reddit_post": "Reddit post", "reddit_comment": "Reddit comment", "playstore_review": "Play Store review",
                "youtube_comment": "YouTube comment"}
SOURCE_GROUP = {"reddit_post": "Reddit", "reddit_comment": "Reddit", "playstore_review": "Play Store", "youtube_comment": "YouTube"}

# Taggers: the engine's two coding rounds (same model family, different instructions). Round 1 covers Reddit only.
TAGGERS = {"r1": "Round 1 (conservative codebook)", "r2": "Round 2 (recall-oriented codebook)"}

PROMPT_VERSIONS = [
    ("Round 1", "CODEBOOK_v1", "Conservative: tag a question only on clear evidence. Reddit posts and comments (2,684 items).",
     "Under-tagged Q4 (what they check), Q8 (segments) and Q9 (unmet needs); rated rich personal posts as partly relevant; called stock-SIP feature requests off-topic."),
    ("Round 2", "CODEBOOK v2", "Recall-oriented: tag whenever the text gives real evidence, even in passing; relevance relaxed for rich personal context. "
     "Re-coded the Reddit items round 1 found relevant, plus Play Store (196) and YouTube (535).",
     "Over-tagged Q9, Q2, Q4 and Q5; the \"needs human help\" tag fired on every Reddit post because posting is itself asking for advice."),
    ("Round 2.1", "CODEBOOK v2.1 (rules applied after coding; the items were not re-coded)",
     "Clarifies three tags after a 20-post read of each: lost trust only when trust in the platform or fund house is stated; confusion only when confusion is "
     "the stated reason; support failure only when contact with support is described. Adds a derived \"hard to use the app\" bucket and sub-themes for the vague buckets.",
     "Applied as text rules in pipeline/rules.py, so the original round 2 coding is unchanged. A re-run with the v2.1 wording would be the cleaner fix."),
]

# ---- quote support check ---------------------------------------------------------------------------------------------------------
# Each item has ONE verified quote that supports its main coding. When a quote is shown under a theme or question, the dashboard prefers
# quotes whose words match that subject (English and Hinglish), and falls back to the best-coded items only when fewer than two match.
import re as _re
_I = _re.I
THEME_LEX = {k: _re.compile(v, _I) for k, v in {
    "STOP_CASH_CRUNCH": r"loan|emi|afford|cash|money|tight|expens|bills|rent|salary|income|broke|paisa|paise|emergency|clear off|left",
    "STOP_OVERCOMMITTED": r"too much|commit|left|in hand|in-hand|emi|loan|expens|reduc|cut|lower|burden|can't manage|cannot manage",
    "STOP_JOB_OR_INCOME_LOSS": r"job|laid off|layoff|resign|salary|income|unemploy|lost|naukri|business|fired",
    "STOP_MARKET_FALL": r"market|crash|fall|down|red|negative|correction|drop|loss|gir",
    "STOP_UNDERWHELMING_RETURNS": r"return|perform|xirr|gain|loss|profit|negative|underperform|flat|nothing|growth",
    "STOP_BETTER_ALTERNATIVE": r"instead|better|switch|moved|direct|stock|etf|index|\bfd\b|real estate|gold|alternative|rather|shift|nifty",
    "STOP_OPS_FAILURE": r"fail|not (?:been )?(?:deducted|processed|debited|executed)|bounce|reject|cancel|error|stuck|pending|autopay|mandate|debit|not (?:getting|able)",
    "PLAT_MANDATE_FAIL": r"autopay|auto pay|mandate|nach|fail|registration|set ?up|reject|bank|cancel",
    "PLAT_EXEC_DELAY": r"delay|late|pending|not (?:executed|processed|allotted)|nav|units|days|not processed",
    "PLAT_NO_CONTROL": r"pause|skip|cancel|edit|modify|can't|cannot|no option|not able|unable|automatic|stop|control|change",
    "PLAT_FORCED_AUTOPAY": r"autopay|auto pay|auto-pay|forced|only option|manual|mandatory",
    "STOP_LOST_TRUST": r"trust|scam|fraud|cheat|unsafe|leave|quit|uninstall|discontinu|never|worst|stopped using|not using",
    "STOP_CONFUSION": r"confus|understand|jargon|don't know|do not know|unsure|not sure|clarity|complicated|samajh",
    "STOP_PASSIVE_DRIFT": r"forgot|forget|lazy|ignore|didn't|did not|stopped|lapsed|not checked|inactive|automatic|skipped",
    "STOP_GOAL_REACHED": r"goal|target|reached|achieved|redeem|completed|done|enough",
    "STOP_FAMILY_ADVICE": r"mom|dad|father|mother|parent|family|wife|husband|friend|brother|advis|told me|brainwash",
    "PLAT_WITHDRAW_DELAY": r"withdraw|redeem|redemption|settle|stuck|days|delay|credit|proceeds|received|money",
    "PLAT_PENALTY_OR_CHARGES": r"charge|penalt|fee|bounce|fine|deduct|₹|\brs\b",
    "PLAT_KYC_BLOCK": r"kyc|verif|document|aadhaar|\bpan\b|reject|nominee|48 hr|pending",
    "PLAT_SUPPORT_FAILURE": r"support|customer care|helpdesk|help desk|ticket|respon|repl|complain|contact|call|supportive",
}.items()}
QUESTION_LEX = {k: _re.compile(v, _I) for k, v in {
    "Q1": r"start|began|goal|plan|future|wealth|reason|because|save|retire|tax|child|house|invest",
    "Q2": r"increase|decrease|step|raise|added|switch|more|less|reduc|started|stopped|changed|now|moved",
    "Q3": r"\b(?:stopped|paused|pausing|stopping|discontinued|cancelled|canceled|skipped|reduced|quit|withdr\w+)\b|because|due to|reason|clear off",
    "Q4": r"check|track|see|view|xirr|nav|portfolio|daily|weekly|monthly|statement|dashboard|gain|loss",
    "Q5": r"worr|confus|afraid|fear|scare|unsure|not sure|doubt|negative|loss|anxious|panic|don't know|stuck",
    "Q6": r"ask|friend|reddit|youtube|advis|google|read|video|forum|consult|family|sheet|app to track|another app",
    "Q7": r"continue|keep|stay|patien|disciplin|long term|consisten|never stopped|still|haven't stopped",
    "Q8": r"\d+ ?(?:yo|years? old|lakh|k\b)|age|salary|income|student|married|kid|parent|loan|emi|in hand|in-hand|job|working",
    "Q9": r"wish|want|need|should|add|feature|option|please|hope|can't|cannot|no way|missing|request|would like|allow|provide|gone",
}.items()}


# ================================================================================================================================
# Changes made after the 20-post review of suspicious tags (data/manual/ai_tag_review.csv) and the pre-publication checklist
# ================================================================================================================================

# ---- platform staff replies are excluded (authors were not stored, so detection is text-based) ---------------------------------
# A staff reply speaks AS the platform ("write to us at", "we sincerely apologise"). A user writing TO support ("Dear Groww Support Team") is kept.
# Play Store developer replies sit in a separate column that never entered the coded text; export.py checks that.
STAFF_REPLY = _re.compile(
    r"(?:please )?feel free to (?:write|reach|contact|mail|email) (?:out )?(?:to )?us|(?:write|reach out|mail|email|dm|contact) (?:to )?us (?:at|on|via|through) "
    r"|we sincerely apologi[sz]e|we apologi[sz]e for (?:the|any) (?:inconvenience|trouble)|we(?:'re| are) (?:really )?sorry to hear"
    r"|thank you for (?:reaching out|contacting us|bringing this|your feedback)|for (?:any )?further assistance,? (?:please|kindly)"
    r"|our (?:support|customer care|care) team (?:will|has|is)|raise a (?:ticket|request) (?:with|through) us|^dear (?:user|customer|investor|valued)\b",
    _I)

# ---- tag rules from the review: a theme stays only when the text actually supports it ------------------------------------------
# Review result (20 items read per tag, 16 for confusion): lost trust 5 wrong + 8 partial, confusion 9 wrong + 4 partial, support failure 5 wrong + 2 partial.
# The wrong ones were: lost trust about holdings or the whole market (not the platform or fund house); confusion tagged on after-the-fact questions;
# support failure on app faults with no mention of support. Each rule below keeps the theme only when the text or a co-tag supports it.
TAG_RULES = {
    "STOP_LOST_TRUST": dict(
        require=_re.compile(r"scam|fraud|fake|cheat|mislead|bhkane|bhatka|distrust|\btrust\b|without (?:my )?(?:consent|permission)|bina permission|hidden charge|"
                            r"\blie\b|\blied\b|unsafe|not safe|bad things|zero hope|worst app|\bloot|thie(?:f|ves)", _I),
        or_cotags=("PLAT_TRUST_LOSS",)),
    "STOP_CONFUSION": dict(
        require=_re.compile(r"confus|(?:don't|do not|didn't|did not|dont|didnt) (?:really )?(?:understand|know what)|no idea|not sure what|samajh (?:nahi|nhi)|jargon|"
                            r"complicated|overwhelm|clueless|too many (?:funds|options|schemes)|\d+ different (?:mutual )?funds|randomly|lost track|blindly", _I),
        or_cotags=()),
    "PLAT_SUPPORT_FAILURE": dict(
        require=_re.compile(r"support|cou?s?tomer (?:care|service|support)|helpdesk|help desk|ticket|call cent|chat option|no response|not respond|no reply|not reply|replied|"
                            r"complaint|escalat|grievance|\bcare\b|resolv|problem solve|solve (?:karta|nahi|nhi)|call (?:receive|uth|pick)|"
                            r"ghatiya service|service (?:is )?(?:very |too )?(?:poor|bad|worst|slow|low)", _I),
        or_cotags=()),
}

# ---- "hard to use the app": a new bucket, built from the Play Store top-issues themes (crash, lag, login loops, confusing layout) ----
APP_USABILITY = "APP_USABILITY"
APP_USABILITY_RE = _re.compile(
    r"not user[- ]?friendly|hard to use|difficult to use|difficult to navigate|confusing (?:app|ui|layout|interface|design)|"
    r"(?:ui|layout|interface|design) (?:is |was )?(?:confusing|bad|poor|worst|cluttered)|(?:app|ui|layout|interface) redesign|redesigned (?:app|ui)|"
    r"(?:app|screen|page|dashboard|website) (?:is |keeps |often |sometimes |some times )?(?:very )?(?:slow|lag|lagging|laggy|hang|hangs|freez\w*|crash\w*)|"
    r"crash(?:es|ing)? (?:and|or) hangs?|hangs? (?:and|or) crash\w*|keeps? crashing|app crash|not loading|won'?t load|something went wrong|"
    r"login (?:issue|problem|error)|unable to log ?in|can'?t log ?in|cannot log ?in|otp (?:not|isn'?t)|after (?:the )?(?:latest|new) update|"
    r"(?:can'?t|cannot|hard to) find (?:the )?(?:option|button|feature|section|tab|menu|page|screen)|app (?:is )?(?:very )?(?:slow|laggy)", _I)
# The first version of this rule matched the bare word "crash" and tagged 28 of 31 items that were about market crashes (found when the quotes
# were read on the Opportunity page). App context is now required for crash, redesign and "cannot find".

# ---- sub-themes: vague parent buckets are split so a reader can see what is inside them -----------------------------------------
# Rule-based, on the verified quote plus the first 600 characters of the text. An item can fall in more than one sub-theme; items matching none are
# shown as "Not specified". Each sub-theme list is ordered from most to least specific.
def _sub(*pairs):
    return [(label, _re.compile(rx, _I)) for label, rx in pairs]


SUBTHEMES = {
    APP_USABILITY: _sub(
        ("Crashes, lag or freezes", r"crash|\blag|hang|freez|slow|not loading|won'?t load|loading"),
        ("Login, OTP or update loops", r"log ?in|otp|\bupdate|reinstall|sign in"),
        ("Confusing layout or redesign", r"confus|layout|redesign|\bui\b|interface|design|cluttered|user[- ]?friendly|navigat"),
        ("Cannot find a feature or screen", r"can'?t find|cannot find|hard to find|where (?:is|to find)|no option"),
        ("Error message or blank screen", r"something went wrong|error|not showing|not displayed|blank")),
    "WORRY_FUND_CHOICE": _sub(
        ("Direct versus regular plan", r"direct|regular plan|commission|expense ratio|distributor|\bagent"),
        ("Index versus active funds", r"index|nifty 50|\bactive\b|passive|\betf"),
        ("Which category, or how to split", r"large ?cap|mid ?cap|small ?cap|flexi|multi ?cap|\bsplit|allocation|categor|sectoral|thematic|portfolio"),
        ("Too many funds or overlap", r"overlap|too many|diversif|duplicate|\d+ (?:different )?funds|\bmany funds"),
        ("Which specific fund", r"which fund|best fund|recommend|suggest|good fund|top fund|\bpick\b"),
        ("Doubts about past performance", r"performance|underperform|track record|rolling|returns? (?:are|is|have|has)")),
    "STOP_BETTER_ALTERNATIVE": _sub(
        ("Cheaper or direct plan", r"direct plan|expense ratio|regular|cheaper"),
        ("Index fund or ETF", r"index|\betf|nifty"),
        ("Direct stocks", r"\bstocks?\b|shares|trading"),
        ("FD, debt, gold or PPF", r"\bfd\b|fixed deposit|debt|gold|\bppf|bond|\bnps|\bepf"),
        ("Property or other assets", r"real estate|property|\bflat\b|\bland\b|crypto"),
        ("Another platform", r"another (?:app|platform)|zerodha|kuvera|\bdhan\b|upstox|paytm|switch(?:ed)? (?:to|from)"),
        ("Lump sum instead of a SIP", r"lump ?sum")),
    "PLAT_NO_CONTROL": _sub(
        ("Cannot pause or skip", r"pause|skip"),
        ("Cannot cancel or stop", r"cancel|\bstop|discontinu"),
        ("Cannot change date or amount", r"\bdate\b|amount|modify|\bedit|change"),
        ("Forced or automatic switch or plan change", r"switch|prime|without (?:my )?(?:consent|permission)|automatic|\bauto\b")),
    "PLAT_SUPPORT_FAILURE": _sub(
        ("No response or very slow", r"no (?:response|reply)|not respond|slow|\bdays\b|waiting|delay"),
        ("Scripted or unhelpful answers", r"script|same (?:answer|reply)|copy|useless|not helpful|unhelpful|generic"),
        ("Ticket raised, not resolved", r"ticket|escalat|complaint|not resolved|unresolved|resolution"),
        ("Cannot reach support by call or chat", r"\bcall|chat|phone|helpline|not pick|unreachable")),
    "STOP_CASH_CRUNCH": _sub(
        ("Loan or EMI", r"loan|\bemi\b|mortgage"),
        ("Rising expenses or low savings", r"expens|bills|rent|afford|\bcost|savings|inflation"),
        ("Income drop or job change", r"income|salary|\bjob\b|laid|unemploy|pay cut|business"),
        ("A big planned spend", r"wedding|\bhouse\b|\bhome\b|\bcar\b|education|marriage|medical|emergency|travel|purchase")),
    "STOP_OPS_FAILURE": _sub(
        ("Debit failed or not deducted", r"not (?:been )?(?:deducted|debited|processed)|fail|bounce|reject"),
        ("Debited but units not allotted", r"debited|not allotted|allot"),
        ("Cancelled SIP still deducted", r"cancel|still (?:deduct|debit|charge)"),
        ("Withdrawal or payout stuck", r"withdraw|redeem|payout|credit|stuck")),
    "PLAT_FEATURE_MISSING": _sub(
        ("STP, SWP or switch", r"\bstp\b|\bswp\b|switch"),
        ("Goal or planning tools", r"goal|planner|planning|calculator|retirement"),
        ("Alerts or reminders", r"alert|reminder|notification|\bsms\b"),
        ("Portfolio view, search or sorting", r"portfolio|holdings|search|\bsort|filter|compare|dashboard|net ?worth"),
        ("SIP options (weekly, step-up, date)", r"weekly|daily|step[- ]?up|top[- ]?up|frequency|sip date|small amount"),
        ("Products missing (NFO, ETF, IPO)", r"\bnfo\b|\betf|\bipo\b|us stocks|international|gold|bond"),
        ("Statements and tax reports", r"statement|report|\btax|capital gain|\bpdf")),
}
SUBTHEME_ALSO_FOR = {"PLAT_FEATURE_MISSING": ("NEED_OTHER",)}      # these themes are pooled with the parent when counting its sub-themes
VAGUE_PARENTS_PAGE2 = [APP_USABILITY, "PLAT_NO_CONTROL", "PLAT_SUPPORT_FAILURE", "STOP_OPS_FAILURE", "STOP_CASH_CRUNCH", "STOP_BETTER_ALTERNATIVE"]
VAGUE_PARENTS_PAGE3 = {"Q5": ["WORRY_FUND_CHOICE"], "Q9": ["PLAT_FEATURE_MISSING"]}

THEME_BRANCH[APP_USABILITY] = "B4"
CAUSE_THEMES.insert(CAUSE_THEMES.index("PLAT_NO_CONTROL") + 1, APP_USABILITY)
FIXABLE[APP_USABILITY] = ("High", "Speed, layout and login problems are product fixes, with no recommendation or nudge involved.")
THEME_LEX[APP_USABILITY] = APP_USABILITY_RE
LABEL_OVERRIDES[APP_USABILITY] = "Hard to use the app"
