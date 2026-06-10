"""
Render a demo GIF for slides: the 6-agent pipeline lighting up step-by-step,
then a committee debate firing (member votes -> verdict). Uses REAL data from a
pipeline run so the numbers are authentic. No browser needed.

Run:  MOCK_MODE=1 python scripts/make_demo_gif.py
Out:  assets/pipeline_debate_demo.gif
"""

import os
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("MOCK_MODE", "1")        # deterministic, offline, fast
os.environ.pop("OPENAI_API_KEY", None)         # templated rationales (cite real numbers)

from pipeline import run_pipeline, AGENTS       # noqa: E402

# ---- palette (matches the dashboard) --------------------------------------
BG = (10, 10, 10); PANEL = (20, 20, 20); CARD = (17, 17, 17); BORDER = (38, 38, 38)
TEXT = (244, 244, 244); MUTED = (138, 138, 138); LIME = (198, 244, 50)
RED = (255, 92, 92); AMBER = (224, 169, 59); DIMGREEN = (47, 58, 23); TRACK = (31, 31, 31)

W, H = 1200, 680
SHORT = ["Market Data", "Technical", "Sentiment", "Risk", "Portfolio", "Explanation"]


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

HEL = "/System/Library/Fonts/Helvetica.ttc"
MENLO = "/System/Library/Fonts/Menlo.ttc"
F_TITLE = font(HEL, 34); F_H = font(HEL, 22); F = font(HEL, 17); F_SM = font(HEL, 14)
M_TAG = font(MENLO, 13); M_SM = font(MENLO, 12); M = font(MENLO, 15); M_B = font(MENLO, 16)


def stance_color(s):
    s = s.upper()
    if s in ("BUY", "POSITIVE", "GOOD", "LOW", "APPROVE"):
        return LIME
    if s in ("SELL", "NEGATIVE", "HIGH", "STALE", "REVISE"):
        return RED
    return AMBER


def base():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # brand
    d.polygon([(40, 38), (47, 56), (65, 63), (47, 70), (40, 88), (33, 70), (15, 63), (33, 56)], fill=LIME)
    d.text((80, 40), "AI Trading Desk", font=F_TITLE, fill=TEXT)
    d.text((82, 80), "24 SUB-AGENTS  ·  6 DEBATE PANELS  ·  4 MCP SERVERS", font=M_TAG, fill=MUTED)
    tag = "2026"
    d.text((W - 40 - d.textlength(tag, font=M_TAG), 44), tag, font=M_TAG, fill=LIME)
    return img, d


def rrect(d, box, radius, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_pipeline(d, states):
    d.text((40, 120), "AGENT PIPELINE", font=M_TAG, fill=MUTED)
    x0, y0, gap, h = 40, 150, 12, 70
    cw = (W - 80 - gap * 5) / 6
    for i, label in enumerate(SHORT):
        x = x0 + i * (cw + gap)
        st = states[i]
        border = LIME if st == "running" else (DIMGREEN if st == "done" else BORDER)
        rrect(d, [x, y0, x + cw, y0 + h], 12, fill=CARD, outline=border, width=2 if st == "running" else 1)
        dot = LIME if st in ("running", "done") else (44, 44, 44)
        cy = y0 + h / 2
        if st == "done":
            d.line([(x + 16, cy), (x + 22, cy + 7), (x + 33, cy - 8)], fill=LIME, width=3)
        else:
            d.ellipse([x + 16, cy - 5, x + 26, cy + 5], fill=dot)
        d.text((x + 42, y0 + 16), f"AGENT {i+1}", font=M_SM, fill=MUTED)
        d.text((x + 42, y0 + 36), label, font=F_SM, fill=LIME if st == "running" else TEXT)


def draw_panel(d, panel, reveal_n, show_verdict):
    px, py, pw = 40, 250, W - 80
    d.text((px, py - 26), f"DEBATE  ·  {panel['title'].upper()}", font=M_TAG, fill=MUTED)
    rrect(d, [px, py, px + pw, py + 400], 14, fill=PANEL, outline=BORDER, width=1)

    # verdict chip
    if show_verdict:
        vc = stance_color(panel["verdict"])
        label = f" {panel['verdict']} · {panel['verdict_confidence']}% "
        wv = d.textlength(label, font=M_B) + 8
        rrect(d, [px + pw - 24 - wv, py + 20, px + pw - 24, py + 50], 8, fill=vc)
        d.text((px + pw - 20 - wv + 4, py + 26), label.strip(), font=M_B, fill=BG)
    d.text((px + 22, py + 24), "Investment Committee votes", font=F_H, fill=TEXT)

    # member cards 2x2
    members = panel["members"]
    gx, gy = 22, 16
    cw = (pw - gx * 3) / 2
    ch = 138
    ox, oy = px + gx, py + 70
    for i, m in enumerate(members):
        if i >= reveal_n:
            continue
        col = i % 2
        row = i // 2
        x = ox + col * (cw + gx)
        y = oy + row * (ch + gy)
        col_c = stance_color(m["stance"])
        rrect(d, [x, y, x + cw, y + ch], 10, fill=CARD, outline=BORDER, width=1)
        d.text((x + 16, y + 14), m["name"], font=F, fill=TEXT)
        # vote chip
        chip = f" {m['stance']} "
        wv = d.textlength(chip, font=M_B) + 6
        rrect(d, [x + cw - 16 - wv, y + 12, x + cw - 16, y + 36], 6, fill=col_c)
        d.text((x + cw - 13 - wv + 3, y + 16), m["stance"], font=M_B, fill=BG)
        # confidence bar
        bx0, bx1, by = x + 16, x + cw - 16, y + 50
        rrect(d, [bx0, by, bx1, by + 6], 3, fill=TRACK)
        fillw = (bx1 - bx0) * m["confidence"] / 100
        rrect(d, [bx0, by, bx0 + fillw, by + 6], 3, fill=col_c)
        # rationale (wrapped)
        wrapped = textwrap.wrap(f"{m['rationale']} ({m['confidence']}%)", width=52)[:3]
        for j, ln in enumerate(wrapped):
            d.text((x + 16, y + 66 + j * 20), ln, font=F_SM, fill=MUTED)


def main():
    results = run_pipeline("ethereum")
    panel = results["panels"]["portfolio"]
    decision = results["portfolio"]["final_decision"]
    conf = results["portfolio"]["confidence"]
    print(f"Decision {decision} {conf}% | committee {panel['tally']}")

    frames, durations = [], []

    def add(img, ms):
        frames.append(img.convert("P", palette=Image.ADAPTIVE))
        durations.append(ms)

    # Phase 1 — pipeline lights up
    states = ["pending"] * 6
    img, d = base(); draw_pipeline(d, states); add(img, 500)
    for i in range(6):
        states[i] = "running"
        img, d = base(); draw_pipeline(d, states); add(img, 420)
        states[i] = "done"
        img, d = base(); draw_pipeline(d, states); add(img, 160)
    img, d = base(); draw_pipeline(d, states); add(img, 700)

    # Phase 2 — committee debate reveals member by member, then verdict
    for n in range(0, 5):
        img, d = base(); draw_pipeline(d, states); draw_panel(d, panel, n, False)
        add(img, 650 if n else 350)
    img, d = base(); draw_pipeline(d, states); draw_panel(d, panel, 4, True)
    add(img, 2600)  # hold on the verdict

    out_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.abspath(os.path.join(out_dir, "pipeline_debate_demo.gif"))
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=durations,
                   loop=0, optimize=True, disposal=2)
    print("Saved", out, f"({len(frames)} frames, {os.path.getsize(out)//1024} KB)")


if __name__ == "__main__":
    main()
