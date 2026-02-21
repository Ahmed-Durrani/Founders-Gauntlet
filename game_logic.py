import json
import os
import re
import time
from functools import lru_cache

from google import genai
from google.genai import types

from personas import LEVELS, THEMES

MODEL_NAME = "gemini-flash-latest"
JUDGMENT_MODEL = MODEL_NAME
STREAM_MODEL = MODEL_NAME
TRANSCRIBE_MODEL = MODEL_NAME

POST_MORTEM_SCORE_KEYS = (
    "confidence",
    "technical_clarity",
    "business_viability",
    "resilience_under_pressure",
)
POST_MORTEM_LIST_LENGTH = 3
POST_MORTEM_LIST_KEYS = ("strengths", "weaknesses", "next_actions")

RETRIEVAL_CHUNK_WORDS = 180
RETRIEVAL_CHUNK_OVERLAP_WORDS = 35
RETRIEVAL_MAX_CHUNK_CHARS = 900
RETRIEVAL_TOP_K = 3

RETRIEVAL_STOPWORDS = {
    "about",
    "after",
    "again",
    "being",
    "below",
    "could",
    "first",
    "founder",
    "from",
    "have",
    "into",
    "just",
    "level",
    "more",
    "next",
    "only",
    "other",
    "same",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "through",
    "under",
    "until",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
}


def _get_client():
    return genai.Client()


def _clean_json_text(raw_text):
    """Removes markdown wrappers so strict JSON parsing can succeed."""
    cleaned_text = (raw_text or "").strip()
    if cleaned_text.startswith("```"):
        first_newline = cleaned_text.find("\n")
        if first_newline != -1:
            cleaned_text = cleaned_text[first_newline:].strip()
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3].strip()
    return cleaned_text


def _safe_load_json(raw_text):
    cleaned_text = _clean_json_text(raw_text)
    return json.loads(cleaned_text)


def _normalize_whitespace(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _tokenize_for_retrieval(text):
    raw_tokens = re.findall(r"[a-z0-9]{3,}", (text or "").lower())
    return [token for token in raw_tokens if token not in RETRIEVAL_STOPWORDS]


@lru_cache(maxsize=8)
def _build_deck_chunks(deck_text):
    """
    Caches chunking for uploaded deck text.
    Output is a tuple so it remains hash-safe for lru_cache.
    """
    normalized = (deck_text or "").strip()
    if not normalized:
        return tuple()

    paragraphs = [
        _normalize_whitespace(part)
        for part in re.split(r"\n\s*\n", normalized)
        if _normalize_whitespace(part)
    ]
    if not paragraphs:
        paragraphs = [_normalize_whitespace(normalized)]

    chunks = []
    current_words = []

    for paragraph in paragraphs:
        paragraph_words = paragraph.split()
        if not paragraph_words:
            continue

        if current_words and len(current_words) + len(paragraph_words) > RETRIEVAL_CHUNK_WORDS:
            chunk_text = " ".join(current_words).strip()
            if chunk_text:
                chunks.append(chunk_text[:RETRIEVAL_MAX_CHUNK_CHARS])

            overlap_words = current_words[-RETRIEVAL_CHUNK_OVERLAP_WORDS:]
            current_words = list(overlap_words)

        current_words.extend(paragraph_words)

    if current_words:
        chunk_text = " ".join(current_words).strip()
        if chunk_text:
            chunks.append(chunk_text[:RETRIEVAL_MAX_CHUNK_CHARS])

    return tuple(chunks[:100])


def _score_chunk(chunk_text, query_tokens):
    if not chunk_text:
        return 0.0

    chunk_tokens = _tokenize_for_retrieval(chunk_text)
    if not chunk_tokens:
        return 0.0

    chunk_token_set = set(chunk_tokens)
    overlap = chunk_token_set.intersection(query_tokens)
    if not overlap:
        return 0.0

    overlap_count = len(overlap)
    frequency_score = sum(chunk_text.lower().count(token) for token in overlap)
    numeric_bonus = 0.5 if re.search(r"\d", chunk_text) else 0.0
    density = overlap_count / max(len(query_tokens), 1)

    return overlap_count + (frequency_score * 0.35) + (density * 2.0) + numeric_bonus


def _retrieve_pitch_deck_context(pitch_deck_text, query_text, top_k=RETRIEVAL_TOP_K):
    """
    Simple local retrieval:
    - chunk deck
    - score chunk relevance by lexical overlap
    - return top excerpts as compact context block
    """
    if not pitch_deck_text:
        return ""

    chunks = _build_deck_chunks(pitch_deck_text)
    if not chunks:
        return ""

    query_tokens = set(_tokenize_for_retrieval(query_text))
    scored_chunks = []

    for chunk in chunks:
        score = _score_chunk(chunk, query_tokens)
        scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda item: item[0], reverse=True)

    selected = [chunk for score, chunk in scored_chunks if score > 0][:top_k]
    if not selected:
        selected = list(chunks[:top_k])

    excerpt_lines = []
    for idx, excerpt in enumerate(selected, start=1):
        excerpt_lines.append(f"[Deck Excerpt {idx}] {excerpt}")

    return "\n\n".join(excerpt_lines)


def _build_deck_instruction(pitch_deck_text, user_input, current_level, startup_theme):
    if not pitch_deck_text:
        return ""

    level_data = LEVELS.get(current_level, {})
    retrieval_query = " ".join(
        [
            str(user_input or ""),
            str(level_data.get("win_condition", "")),
            str(level_data.get("style", "")),
            str(startup_theme),
        ]
    )
    deck_context = _retrieve_pitch_deck_context(pitch_deck_text, retrieval_query)
    if not deck_context:
        return ""

    return f"""
    PITCH DECK RAG CONTEXT (retrieved excerpts):
    {deck_context}

    RAG RULES:
    - Cross-reference user claims with the deck excerpts.
    - If claims conflict with deck evidence, challenge the mismatch explicitly.
    - If claims align, acknowledge alignment and push on depth or feasibility.
    """


def _default_post_mortem_report():
    return {
        "scores": {
            "confidence": 50,
            "technical_clarity": 50,
            "business_viability": 50,
            "resilience_under_pressure": 50,
        },
        "strengths": [
            "Maintained engagement with the persona.",
            "Provided at least one concrete response.",
            "Stayed within the game loop until completion.",
        ],
        "weaknesses": [
            "Analysis unavailable due to model parsing error.",
            "Technical depth assessment could not be computed.",
            "Business-case quality assessment could not be computed.",
        ],
        "next_actions": [
            "Replay the same theme and answer each challenge with one metric.",
            "Use a tighter structure: problem, solution, proof, ask.",
            "Test your pitch with one skeptical technical question per round.",
        ],
        "summary": "Automatic report generation failed, so fallback coaching was provided.",
    }


def _clamp_score(value, default_value):
    if isinstance(value, bool):
        return default_value
    try:
        numeric = int(float(value))
    except (TypeError, ValueError):
        numeric = default_value
    return max(0, min(100, numeric))


def _normalize_list_items(value, fallback_items):
    normalized = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                cleaned = item.strip()
            elif item is None:
                cleaned = ""
            else:
                cleaned = str(item).strip()
            if cleaned:
                normalized.append(cleaned)
            if len(normalized) >= POST_MORTEM_LIST_LENGTH:
                break

    for fallback_item in fallback_items:
        if len(normalized) >= POST_MORTEM_LIST_LENGTH:
            break
        normalized.append(fallback_item)

    return normalized[:POST_MORTEM_LIST_LENGTH]


def _normalize_post_mortem_report(report):
    """Coerces any parseable output to the dashboard schema contract."""
    fallback = _default_post_mortem_report()
    if not isinstance(report, dict):
        return fallback

    scores_input = report.get("scores")
    if not isinstance(scores_input, dict):
        scores_input = {}

    normalized_scores = {}
    for key in POST_MORTEM_SCORE_KEYS:
        normalized_scores[key] = _clamp_score(
            scores_input.get(key),
            fallback["scores"][key],
        )

    summary_value = report.get("summary")
    if isinstance(summary_value, str) and summary_value.strip():
        summary = summary_value.strip()
    else:
        summary = fallback["summary"]

    normalized = {
        "scores": normalized_scores,
        "summary": summary,
    }
    for list_key in POST_MORTEM_LIST_KEYS:
        normalized[list_key] = _normalize_list_items(
            report.get(list_key),
            fallback[list_key],
        )
    return normalized


def _is_valid_post_mortem_report(report):
    if not isinstance(report, dict):
        return False

    required_top_keys = {"scores", "strengths", "weaknesses", "next_actions", "summary"}
    if not required_top_keys.issubset(report.keys()):
        return False

    scores = report.get("scores")
    if not isinstance(scores, dict):
        return False
    for key in POST_MORTEM_SCORE_KEYS:
        value = scores.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            return False
        if value < 0 or value > 100:
            return False

    for list_key in POST_MORTEM_LIST_KEYS:
        value = report.get(list_key)
        if not isinstance(value, list) or len(value) != POST_MORTEM_LIST_LENGTH:
            return False
        for item in value:
            if not isinstance(item, str) or not item.strip():
                return False

    summary = report.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return False

    return True


def _build_post_mortem_prompt(startup_theme, theme_data, outcome, transcript_text, deck_context):
    deck_block = (
        f"\nPITCH DECK EVIDENCE (RAG EXCERPTS):\n{deck_context}\n"
        if deck_context
        else "\nPITCH DECK EVIDENCE (RAG EXCERPTS): none provided\n"
    )

    return f"""
    You are an expert startup pitch coach.
    Analyze the transcript and return ONLY valid JSON matching the exact schema below.

    Selected Theme: {startup_theme}
    Theme Context: {theme_data['description']}
    Final Outcome: {outcome}
    {deck_block}
    TRANSCRIPT:
    {transcript_text}

    JSON SCHEMA:
    {{
      "scores": {{
        "confidence": <int 0-100>,
        "technical_clarity": <int 0-100>,
        "business_viability": <int 0-100>,
        "resilience_under_pressure": <int 0-100>
      }},
      "strengths": [
        "<short bullet>",
        "<short bullet>",
        "<short bullet>"
      ],
      "weaknesses": [
        "<short bullet>",
        "<short bullet>",
        "<short bullet>"
      ],
      "next_actions": [
        "<specific practice action>",
        "<specific practice action>",
        "<specific practice action>"
      ],
      "summary": "<1-2 sentence summary>"
    }}

    HARD RULES:
    - Output strictly valid JSON only.
    - Keep strengths/weaknesses/next_actions exactly 3 items each.
    - Use concise and specific coaching language.
    - Reference contradictions between transcript claims and deck evidence when relevant.
    """


def _build_post_mortem_repair_prompt(raw_output, validation_error):
    return f"""
    You are a strict JSON repair utility.
    Convert the provided output into valid JSON that matches this exact schema and return JSON only.

    JSON SCHEMA:
    {{
      "scores": {{
        "confidence": <int 0-100>,
        "technical_clarity": <int 0-100>,
        "business_viability": <int 0-100>,
        "resilience_under_pressure": <int 0-100>
      }},
      "strengths": ["<text>", "<text>", "<text>"],
      "weaknesses": ["<text>", "<text>", "<text>"],
      "next_actions": ["<text>", "<text>", "<text>"],
      "summary": "<text>"
    }}

    Validation Error:
    {validation_error}

    Output to repair:
    {raw_output}

    Rules:
    - Output only JSON.
    - Keep strengths/weaknesses/next_actions to exactly 3 non-empty strings.
    - Ensure all score values are integers from 0 to 100.
    """


def initialize_ai():
    """Checks for API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("DEBUG: GEMINI_API_KEY is missing.")
        return None
    return True


def get_theme_data(theme_name):
    """Returns safe theme config for prompt injection."""
    return THEMES.get(theme_name, THEMES["General SaaS"])


def _build_roleplay_instruction(current_level, startup_theme, theme_data):
    level_data = LEVELS.get(current_level, {})
    focus_areas = ", ".join(theme_data.get("focus_areas", []))

    return f"""
    You are roleplaying a startup pitch obstacle.

    CHARACTER DETAILS:
    Role: {level_data.get('role', '')}
    Style: {level_data.get('style', '')}
    Win Condition: {level_data.get('win_condition', '')}

    STARTUP THEME CONTEXT:
    Theme: {startup_theme}
    Theme Description: {theme_data.get('description', '')}
    Mandatory Challenge Areas: {focus_areas}

    RESPONSE RULES:
    - Stay in character and challenge the founder based on this level.
    - Tailor skepticism to the selected startup theme.
    - Ask pointed follow-up questions when needed.
    - Output plain conversational text only.
    """


def _build_judgment_instruction(current_level, startup_theme, theme_data):
    level_data = LEVELS.get(current_level, {})
    focus_areas = ", ".join(theme_data.get("focus_areas", []))

    return f"""
    You are a startup pitch game judge.
    Evaluate the user's latest response based on the context.

    CHARACTER DETAILS:
    Role: {level_data.get('role', '')}
    Style: {level_data.get('style', '')}
    Win Condition: {level_data.get('win_condition', '')}

    STARTUP THEME CONTEXT:
    Theme: {startup_theme}
    Theme Description: {theme_data.get('description', '')}
    Mandatory Challenge Areas: {focus_areas}

    JUDGING RULES:
    - If the user answer is weak or violates constraints: damage is -10 or -20.
    - If the user answer satisfies the win condition: level_passed is true.
    - Otherwise: damage is 0 and level_passed is false.
    """


def _recover_streamed_reply(reply_prompt, partial_text, stream_error):
    """
    Recovery path for interrupted streams.
    Returns continuation text (or full text if no partial exists).
    """
    recovery_prompt = f"""
    {reply_prompt}

    RECOVERY MODE:
    The previous streaming response was interrupted.
    Stream error: {stream_error}

    PARTIAL_REPLY_ALREADY_SHOWN:
    {partial_text}

    INSTRUCTIONS:
    - Output plain conversational text only.
    - If PARTIAL_REPLY_ALREADY_SHOWN is empty: generate the full investor reply.
    - If PARTIAL_REPLY_ALREADY_SHOWN is not empty: continue from exactly where it ended.
    - Do not repeat prior text.
    """

    for attempt in range(2):
        try:
            client = _get_client()
            response = client.models.generate_content(
                model=STREAM_MODEL,
                contents=recovery_prompt,
            )
            return (response.text or "").strip()
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Quota" in error_str:
                print(f"Quota hit in stream recovery. Waiting 2 seconds... (Attempt {attempt + 1}/2)")
                time.sleep(2)
                continue
            print(f"STREAM RECOVERY ERROR: {e}")
            return ""

    return ""


def stream_investor_reply(user_input, current_level, chat_history, startup_theme, pitch_deck_text=""):
    """
    Streams only the investor dialogue text token-by-token for low-latency UX.
    Mechanics (damage / pass) should be requested separately via get_turn_judgment.
    """
    theme_data = get_theme_data(startup_theme)
    roleplay_instruction = _build_roleplay_instruction(current_level, startup_theme, theme_data)
    deck_instruction = _build_deck_instruction(
        pitch_deck_text, user_input, current_level, startup_theme
    )
    history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])

    reply_prompt = f"""
    {roleplay_instruction}
    {deck_instruction}

    CURRENT CHAT HISTORY:
    {history_text}

    USER'S NEW INPUT:
    {user_input}

    TASK:
    - Respond as the current investor persona in natural conversational text only.
    - Do not include JSON.
    - Keep your response concise and sharp (2-5 sentences).
    """

    def _token_generator():
        partial_chunks = []
        try:
            client = _get_client()
            response_stream = client.models.generate_content_stream(
                model=STREAM_MODEL,
                contents=reply_prompt,
            )
            for chunk in response_stream:
                text = chunk.text or ""
                if text:
                    partial_chunks.append(text)
                    yield text
            return
        except Exception as stream_error:
            partial_text = "".join(partial_chunks).strip()
            if partial_text:
                yield "\n\n*(Connection jitter detected. Recovering remaining text...)*\n\n"
            else:
                yield "*(Reconnecting to investor response...)* "

            recovered = _recover_streamed_reply(
                reply_prompt=reply_prompt,
                partial_text=partial_text,
                stream_error=str(stream_error),
            )
            if not recovered:
                if partial_text:
                    yield "\n*(Reply may be partial due to a temporary connection issue.)*"
                else:
                    yield "*(The investor pauses, unable to respond right now. Try again.)*"
                return

            cleaned_recovered = recovered
            if partial_text:
                if cleaned_recovered.startswith(partial_text):
                    cleaned_recovered = cleaned_recovered[len(partial_text):]
                elif len(partial_text) > 80:
                    tail = partial_text[-80:]
                    if cleaned_recovered.startswith(tail):
                        cleaned_recovered = cleaned_recovered[len(tail):]

            cleaned_recovered = cleaned_recovered.lstrip()
            if cleaned_recovered:
                yield cleaned_recovered

    return _token_generator()


def get_turn_judgment(user_input, current_level, chat_history, startup_theme, pitch_deck_text=""):
    """
    Returns strict mechanics JSON after a streamed investor reply.
    Output schema:
    {
      "damage": 0 | -10 | -20,
      "level_passed": bool,
      "feedback": "..."
    }
    """
    theme_data = get_theme_data(startup_theme)
    judgment_instruction = _build_judgment_instruction(current_level, startup_theme, theme_data)
    deck_instruction = _build_deck_instruction(
        pitch_deck_text, user_input, current_level, startup_theme
    )
    history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])

    judgment_prompt = f"""
    {judgment_instruction}
    {deck_instruction}

    CURRENT CHAT HISTORY:
    {history_text}

    USER'S NEW INPUT:
    {user_input}

    TASK:
    Output strict JSON only with this schema:
    {{
      "damage": <int: 0, -10, -20>,
      "level_passed": <boolean>,
      "feedback": "<short rationale>"
    }}
    """

    for attempt in range(3):
        try:
            client = _get_client()
            response = client.models.generate_content(
                model=JUDGMENT_MODEL,
                contents=judgment_prompt,
            )
            raw_text = response.text or ""
            game_data = _safe_load_json(raw_text)

            damage = game_data.get("damage", 0)
            try:
                damage = int(damage)
            except (TypeError, ValueError):
                damage = 0
            if damage not in (0, -10, -20):
                damage = -20 if damage < -10 else (-10 if damage < 0 else 0)

            level_passed = bool(game_data.get("level_passed", False))
            feedback = str(game_data.get("feedback", "")).strip()

            return {
                "damage": damage,
                "level_passed": level_passed,
                "feedback": feedback,
            }
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Quota" in error_str:
                print(f"Quota hit in judgment. Waiting 3 seconds... (Attempt {attempt + 1}/3)")
                time.sleep(3)
                continue
            print(f"JUDGMENT ERROR: {e}")
            return {
                "damage": 0,
                "level_passed": False,
                "feedback": f"System error: {e}",
            }

    return {
        "damage": 0,
        "level_passed": False,
        "feedback": "Model overloaded. Judgment unavailable.",
    }


def get_ai_response(user_input, current_level, chat_history, startup_theme, pitch_deck_text=""):
    """
    Backward-compatible helper.
    Uses turn judgment path and provides a placeholder reply.
    """
    judgment = get_turn_judgment(
        user_input=user_input,
        current_level=current_level,
        chat_history=chat_history,
        startup_theme=startup_theme,
        pitch_deck_text=pitch_deck_text,
    )
    return {
        "reply": "Streaming mode active. Investor reply is generated separately.",
        "damage": judgment["damage"],
        "level_passed": judgment["level_passed"],
        "feedback": judgment.get("feedback", ""),
    }


def transcribe_pitch_audio(audio_bytes, mime_type="audio/wav"):
    """
    Transcribes microphone input to text using Gemini multimodal support.
    Returns plain text transcript or empty string on failure.
    """
    if not audio_bytes:
        return ""

    safe_mime = (mime_type or "audio/wav").strip() or "audio/wav"
    prompt_part = types.Part.from_text(
        text=(
            "Transcribe this founder pitch audio to plain text. "
            "Return only the spoken transcript. "
            "Do not add commentary."
        )
    )
    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=safe_mime)

    for attempt in range(3):
        try:
            client = _get_client()
            response = client.models.generate_content(
                model=TRANSCRIBE_MODEL,
                contents=[prompt_part, audio_part],
            )
            transcript = _normalize_whitespace(response.text or "")
            if transcript:
                return transcript
            raise ValueError("Empty transcript.")
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Quota" in error_str:
                print(f"Quota hit in transcription. Waiting 3 seconds... (Attempt {attempt + 1}/3)")
                time.sleep(3)
                continue
            print(f"TRANSCRIPTION ERROR: {e}")
            return ""

    return ""


def get_post_mortem_analysis(chat_history, startup_theme, outcome, pitch_deck_text=""):
    """
    Phase 1.1 + Phase 2:
    - strict JSON validation / repair / normalization
    - includes pitch deck RAG excerpts in evaluation context
    """
    client = _get_client()
    theme_data = get_theme_data(startup_theme)
    transcript_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])

    deck_query = f"{outcome}\n{transcript_text[:4000]}"
    deck_context = _retrieve_pitch_deck_context(pitch_deck_text, deck_query, top_k=4)

    generation_prompt = _build_post_mortem_prompt(
        startup_theme,
        theme_data,
        outcome,
        transcript_text,
        deck_context,
    )

    best_candidate = None
    last_error = None

    for attempt in range(3):
        raw_output = ""

        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=generation_prompt)
            raw_output = response.text or ""
            candidate = _safe_load_json(raw_output)
            best_candidate = candidate

            if _is_valid_post_mortem_report(candidate):
                return _normalize_post_mortem_report(candidate)

            raise ValueError("Schema validation failed for initial post-mortem output.")

        except Exception as first_error:
            last_error = first_error

            try:
                repair_prompt = _build_post_mortem_repair_prompt(raw_output, str(first_error))
                repair_response = client.models.generate_content(model=MODEL_NAME, contents=repair_prompt)
                repaired_output = repair_response.text or ""
                repaired_candidate = _safe_load_json(repaired_output)
                best_candidate = repaired_candidate

                if _is_valid_post_mortem_report(repaired_candidate):
                    return _normalize_post_mortem_report(repaired_candidate)

                raise ValueError("Schema validation failed for repaired post-mortem output.")

            except Exception as repair_error:
                last_error = repair_error
                error_str = str(repair_error)
                if "429" in error_str or "Quota" in error_str:
                    print(f"Quota hit during post-mortem. Waiting 5 seconds... (Attempt {attempt + 1}/3)")
                    time.sleep(5)
                continue

    if best_candidate is not None:
        print("Post-mortem schema not fully valid after retries. Returning normalized candidate.")
        return _normalize_post_mortem_report(best_candidate)

    print(f"Post-mortem analysis failed after retries: {last_error}")
    return _default_post_mortem_report()
