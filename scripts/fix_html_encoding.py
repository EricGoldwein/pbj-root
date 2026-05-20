"""One-off: re-encode cp1252-mislabeled HTML to UTF-8 and patch press page copy/modal."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PRESS_MODAL_CSS = """
    .press-contact-overlay {
      display: none;
      position: fixed;
      inset: 0;
      z-index: 10000;
      background: rgba(0, 0, 0, 0.5);
      align-items: center;
      justify-content: center;
      padding: 1rem;
      box-sizing: border-box;
    }
    .press-contact-overlay[aria-hidden="false"] {
      display: flex !important;
    }
    .press-contact-dialog {
      position: relative;
      background: #1e293b;
      border: 1px solid rgba(96, 165, 250, 0.25);
      border-radius: 12px;
      max-width: 440px;
      width: 100%;
      max-height: calc(100vh - 2rem);
      overflow: auto;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
      color: #e2e8f0;
    }
    .press-contact-dialog h2 {
      margin: 0;
      padding: 1.25rem 2.75rem 0 1.25rem;
      font-size: 1.25rem;
      color: #60a5fa;
      line-height: 1.3;
    }
    .press-contact-close {
      position: absolute;
      top: 0.75rem;
      right: 0.75rem;
      width: 44px;
      height: 44px;
      padding: 0;
      border: none;
      background: transparent;
      cursor: pointer;
      font-size: 1.75rem;
      line-height: 1;
      color: rgba(148, 163, 184, 0.95);
      font-family: system-ui, sans-serif;
    }
    .press-contact-close:hover { color: #e2e8f0; }
    .press-contact-close:focus-visible {
      outline: 2px solid #60a5fa;
      outline-offset: 2px;
    }
    .press-contact-form {
      padding: 1rem 1.25rem 1.5rem;
    }
    .press-contact-form .f-group {
      margin-bottom: 1rem;
    }
    .press-contact-form label {
      display: block;
      font-weight: 500;
      color: #cbd5e1;
      margin-bottom: 0.3rem;
      font-size: 0.9rem;
    }
    .press-contact-form input[type="text"],
    .press-contact-form input[type="email"],
    .press-contact-form textarea {
      width: 100%;
      padding: 0.6rem 0.75rem;
      border: 1px solid rgba(96, 165, 250, 0.35);
      border-radius: 8px;
      font: inherit;
      font-size: 1rem;
      box-sizing: border-box;
      background: rgba(15, 23, 42, 0.6);
      color: #e2e8f0;
    }
    .press-contact-form textarea {
      min-height: 100px;
      resize: vertical;
    }
    .press-contact-form input::placeholder,
    .press-contact-form textarea::placeholder {
      color: rgba(148, 163, 184, 0.75);
    }
    .press-contact-form input:focus,
    .press-contact-form textarea:focus {
      outline: none;
      border-color: rgba(96, 165, 250, 0.7);
      box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.25);
    }
    .press-contact-form input:-webkit-autofill,
    .press-contact-form input:-webkit-autofill:hover,
    .press-contact-form input:-webkit-autofill:focus,
    .press-contact-form input:-webkit-autofill:active,
    .press-contact-form textarea:-webkit-autofill,
    .press-contact-form textarea:-webkit-autofill:hover,
    .press-contact-form textarea:-webkit-autofill:focus,
    .press-contact-form textarea:-webkit-autofill:active {
      -webkit-text-fill-color: #e2e8f0 !important;
      -webkit-box-shadow: 0 0 0 1000px rgb(15, 23, 42) inset !important;
      box-shadow: 0 0 0 1000px rgb(15, 23, 42) inset !important;
      transition: background-color 5000s ease-in-out 0s;
    }
    .press-contact-form .f-row-submit {
      display: flex;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
      margin-top: 0.75rem;
    }
    .press-contact-form .cb-wrap {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      cursor: pointer;
      color: #cbd5e1;
    }
    .press-contact-form button[type="submit"] {
      background: rgba(96, 165, 250, 0.2);
      color: #93c5fd;
      border: 1px solid rgba(96, 165, 250, 0.5);
      padding: 0.7rem 1.25rem;
      border-radius: 8px;
      font: inherit;
      font-size: 1rem;
      font-weight: 500;
      cursor: pointer;
      min-height: 44px;
    }
    .press-contact-form button[type="submit"]:hover {
      background: rgba(96, 165, 250, 0.3);
      color: #e0e7ff;
    }
"""

PRESS_MODAL_HTML = """
  <div id="press-contact-overlay" class="press-contact-overlay" aria-hidden="true">
    <div class="press-contact-dialog" role="dialog" aria-labelledby="press-contact-title" aria-modal="true">
      <h2 id="press-contact-title">Request PBJ analysis</h2>
      <button type="button" class="press-contact-close" aria-label="Close">&times;</button>
      <form action="/contact" method="POST" class="press-contact-form">
        <input type="hidden" name="csrf_token" id="press-csrf" value="">
        <input type="hidden" name="next" value="/press">
        <div class="f-group">
          <label for="press-name">Name <span style="color:#f87171">*</span></label>
          <input type="text" id="press-name" name="name" required autocomplete="name" maxlength="200">
        </div>
        <div class="f-group">
          <label for="press-email">Email <span style="color:#f87171">*</span></label>
          <input type="email" id="press-email" name="email" required autocomplete="email">
        </div>
        <div class="f-group">
          <label for="press-message">Message <span style="color:#f87171">*</span></label>
          <textarea id="press-message" name="message" required placeholder="Your inquiry (topic, deadline, outlet)"></textarea>
        </div>
        <div class="f-row-submit">
          <label class="cb-wrap">
            <input type="checkbox" name="press" id="press-media-checkbox" value="yes" checked>
            <span>I am media</span>
          </label>
          <button type="submit">Send</button>
        </div>
      </form>
    </div>
  </div>
"""


def _decode_html_bytes(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _has_mojibake(data: bytes) -> bool:
    if b"\x97" in data or b"\x85" in data:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return True
        # UTF-8 valid but cp1252 punctuation bytes present (mislabeled file)
        if re.search(rb"(?<![\x80-\xBF])\x97(?![\x80-\xBF])", data):
            return True
        if re.search(rb'placeholder="[^"]*\x85', data):
            return True
        if re.search(rb'press-contact-close[^>]*>\xd7</button>', data):
            return True
    return False


def fix_press() -> None:
    path = ROOT / "press.html"
    text = _decode_html_bytes(path.read_bytes())

    text = text.replace(
        'content="For journalists covering nursing homes, staffing, and ownership. PBJ data expert Eric Goldwein \x97 background briefings',
        'content="For journalists covering nursing homes, staffing, and ownership. PBJ data expert Eric Goldwein: background briefings',
    )
    # After cp1252 decode, em dash is \u2014
    text = re.sub(
        r"<li><strong>PBJ briefings &amp; methodology guidance</strong>\s*[\u2014\uFFFD]\s*How the data works.*?No commitment required\.</li>",
        "<li><strong>PBJ briefings &amp; methodology guidance.</strong> How the data works, what it measures, where it breaks down, and common misreads.</li>",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"<li><strong>Facility, ownership &amp; trend analysis</strong>\s*[\u2014\uFFFD]\s*",
        "<li><strong>Facility, ownership &amp; trend analysis.</strong> ",
        text,
    )
    text = re.sub(
        r"<li><strong>Verification &amp; quotes</strong>\s*[\u2014\uFFFD]\s*",
        "<li><strong>Verification &amp; quotes.</strong> ",
        text,
    )
    text = text.replace(
        "Seagate Rehabilitation and Nursing Center \u2014 Daily",
        "Seagate Rehabilitation and Nursing Center: daily",
    )
    text = text.replace(
        "WTVR CBS 6 (Richmond) \u2014 Twin Lakes",
        "WTVR CBS 6 (Richmond): Twin Lakes",
    )
    text = text.replace(
        'Eric Goldwein \u2014 background',
        'Eric Goldwein: background',
    )

    if PRESS_MODAL_CSS.strip() not in text:
        text = text.replace("  </style>\n</head>", PRESS_MODAL_CSS + "  </style>\n</head>", 1)

    # Replace modal block
    text = re.sub(
        r'\n  <div id="press-contact-overlay".*?</div>\n\n  <footer class="footer"',
        "\n" + PRESS_MODAL_HTML + "\n  <footer class=\"footer\"",
        text,
        count=1,
        flags=re.DOTALL,
    )

    path.write_text(text, encoding="utf-8", newline="\n")
    print("fixed press.html")


def fix_other_html() -> None:
    for path in sorted(ROOT.rglob("*.html")):
        if path.name == "press.html":
            continue
        s = str(path)
        if "node_modules" in s or ".git" in s:
            continue
        data = path.read_bytes()
        if not _has_mojibake(data):
            continue
        text = _decode_html_bytes(data)
        # Normalize lone 0xd7 close buttons to entity when in button text
        text = re.sub(
            r'(class="[^"]*close[^"]*"[^>]*>)\xd7(</button>)',
            r"\1&times;\2",
            text,
        )
        path.write_text(text, encoding="utf-8", newline="\n")
        print("re-encoded", path.relative_to(ROOT))


if __name__ == "__main__":
    fix_press()
    fix_other_html()
