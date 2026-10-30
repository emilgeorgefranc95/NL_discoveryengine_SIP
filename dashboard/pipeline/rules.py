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
