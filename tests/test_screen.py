"""Phase 5 screens (architecture.md, steps 2-3). Run:  .venv/bin/python -m pytest tests/test_screen.py -q"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import screen as S  # noqa: E402

REFUSED = [
    ("Should I stop my SIP?", "advice"), ("Which fund should I buy?", "advice"),
    ("Is it a good time to invest in mutual funds?", "advice"), ("What is the best mutual fund to invest in?", "advice"),
    ("recommend me a fund", "advice"), ("Should we increase our SIP?", "advice"), ("what should I do with my SIP", "advice"),
    ("Top 5 mutual funds to buy", "advice"), ("Which fund to pick?", "advice"), ("Which fund do you recommend?", "advice"),
    ("Will the market recover this year?", "prediction"), ("Predict the Nifty for next month", "prediction"),
    ("Market kab girega?", "prediction"),
    ("Calculate my SIP returns for 10 years", "returns"), ("Which fund gave the highest returns?", "returns"),
    ("Compare returns of HDFC and SBI funds", "returns"),
    ("how much will I get if I invest 5000 monthly for 20 years", "returns"),
    ("SIP band kar dun ya chalu rakhun?", "advice"), ("mujhe konsa fund lena chahiye", "advice"),
    ("क्या मुझे SIP बंद कर देना चाहिए", "advice"),
]
ALLOWED = [
    "Why do investors ask which fund is best for them?",
    "Why do people stop their SIP?", "What leads investors to pause, reduce or stop a SIP?",
    "What do people say about SIP returns being lower than expected?", "What do users suggest the app should add?",
    "Why do people say the market fall made them stop?", "What do SIP investors check once they have started?",
    "What unmet needs do SIP investors have?", "What do people recommend to beginners?", "SIP kyun band karte hain log?",
    "SIP ka autopay fail ho gaya, log kya karte hain?", "What separates investors who continue from those who drop off?",
    "Why did people redeem their mutual funds?", "How do people decide which fund to pick?",
    "What do investors worry about when the market crashes?", "Do people compare apps before starting a SIP?",
    "What do people expect from a SIP?",
]


@pytest.mark.parametrize("q,kind", REFUSED)
def test_advice_prediction_and_returns_requests_are_refused(q, kind):
    assert S.screen_advice(q) == kind


@pytest.mark.parametrize("q", ALLOWED)
def test_questions_about_what_people_say_are_not_refused(q):
    assert S.screen_advice(q) is None


@pytest.mark.parametrize("q", [
    "My PAN is ABCDE1234F", "call me on 9876543210", "email me at a.b@gmail.com", "my account number 123456789012",
    "aadhaar 1234 5678 9012", "my otp is 482913", "card 4111 1111 1111 1111", "+91 98765 43210 is my number",
])
def test_personal_details_are_detected(q):
    assert S.screen_pii(q)


@pytest.mark.parametrize("q", ALLOWED + ["I invest 5000 rupees every month", "I started in 2021 with 1000 per month",
                                         "SIP of ₹10,00,000", "returns of 12% over 10 years"])
def test_ordinary_numbers_are_not_flagged_as_personal_details(q):
    assert S.screen_pii(q) == []


def test_pii_result_never_contains_the_value():
    assert all("9876543210" not in str(x) for x in S.screen_pii("call 9876543210"))
