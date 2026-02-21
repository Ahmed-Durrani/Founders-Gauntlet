import base64
import hashlib
import io
import json
import math
import struct
import wave
from functools import lru_cache

import streamlit.components.v1 as components


def _build_wav_data_uri(samples, sample_rate=22050):
    pcm_frames = b"".join(struct.pack("<h", max(-32767, min(32767, int(s)))) for s in samples)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_frames)
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:audio/wav;base64,{b64}"


def _generate_damage_samples(sample_rate=22050):
    duration = 0.34
    total = int(duration * sample_rate)
    out = []
    for i in range(total):
        t = i / sample_rate
        decay = math.exp(-9.5 * t)
        wobble = 0.85 * math.sin(2 * math.pi * 72 * t)
        sub = 0.45 * math.sin(2 * math.pi * 42 * t)
        grit = 0.16 * math.sin(2 * math.pi * 190 * t)
        out.append((wobble + sub + grit) * decay * 25000)
    return out


def _generate_win_samples(sample_rate=22050):
    duration = 0.42
    total = int(duration * sample_rate)
    out = []
    for i in range(total):
        t = i / sample_rate
        decay = math.exp(-4.6 * t)
        tone_a = math.sin(2 * math.pi * 988 * t)
        tone_b = math.sin(2 * math.pi * 1318 * t)
        tone_c = math.sin(2 * math.pi * 1568 * t)
        sparkle = 0.35 * math.sin(2 * math.pi * 2489 * t)
        value = (0.42 * tone_a + 0.33 * tone_b + 0.25 * tone_c + sparkle) * decay
        out.append(value * 21000)
    return out


@lru_cache(maxsize=4)
def get_sound_data_uri(effect_name):
    if effect_name == "damage":
        return _build_wav_data_uri(_generate_damage_samples())
    if effect_name == "valuation":
        return _build_wav_data_uri(_generate_win_samples())
    return ""


def play_hidden_sound(effect_name, nonce):
    data_uri = get_sound_data_uri(effect_name)
    if not data_uri:
        return
    element_id = f"fx_{effect_name}_{nonce}"
    html = f"""
<audio id="{element_id}" autoplay preload="auto" style="display:none;">
  <source src="{data_uri}" type="audio/wav" />
</audio>
<script>
  const el = document.getElementById("{element_id}");
  if (el) {{
    const p = el.play();
    if (p && p.catch) {{
      p.catch(() => {{}});
    }}
  }}
</script>
"""
    components.html(html, height=0, width=0)


def trigger_haptic_feedback(pattern, nonce):
    safe_pattern = pattern if isinstance(pattern, list) and pattern else [120]
    pattern_js = json.dumps(safe_pattern)
    html = f"""
<script>
  (function() {{
    try {{
      const pattern = {pattern_js};
      if (navigator.vibrate) {{
        navigator.vibrate(pattern);
      }}
    }} catch (e) {{}}
  }})();
</script>
<div id="haptic-{nonce}" style="display:none;"></div>
"""
    components.html(html, height=0, width=0)


def render_copy_button(share_text, label="Copy Share Text"):
    encoded = base64.b64encode((share_text or "").encode("utf-8")).decode("ascii")
    stable_hash = hashlib.md5((share_text or "").encode("utf-8")).hexdigest()[:10]
    button_id = f"copy-share-{stable_hash}"
    status_id = f"copy-status-{stable_hash}"

    html = f"""
<button id="{button_id}" style="
  width:100%;
  min-height:48px;
  border:none;
  border-radius:12px;
  font-weight:700;
  cursor:pointer;
  background:#121826;
  color:#f5f7ff;
">{label}</button>
<div id="{status_id}" style="font-size:0.85rem; color:#6b7280; margin-top:0.4rem;"></div>
<script>
  const btn = document.getElementById("{button_id}");
  const status = document.getElementById("{status_id}");
  const payload = atob("{encoded}");

  async function copyText() {{
    try {{
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        await navigator.clipboard.writeText(payload);
      }} else {{
        const ta = document.createElement("textarea");
        ta.value = payload;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }}
      status.textContent = "Copied to clipboard.";
      btn.textContent = "Copied";
      setTimeout(() => {{
        btn.textContent = "{label}";
      }}, 1200);
    }} catch (e) {{
      status.textContent = "Clipboard blocked. Copy from the text box below.";
    }}
  }}

  if (btn) {{
    btn.addEventListener("click", copyText);
  }}
</script>
"""
    components.html(html, height=86)
