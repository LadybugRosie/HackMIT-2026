"""
Auto-Grading Service - AI-Powered Rubric-Based Grading
Uses OpenAI GPT-4o for high-accuracy grading with vision support.
Supports multimodal submissions (text + images).
Only evaluates submissions with trust score >= 60%.
"""
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import httpx

# OpenAI API configuration
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


def _get_openai_key():
    return os.getenv("OPENAI_API_KEY")


def _get_openai_model():
    """Use gpt-4o for auto-grading (more accurate, better rubric adherence).
    Falls back to OPENAI_MODEL env var if set."""
    return os.getenv("OPENAI_MODEL", "gpt-4o")


def format_rubric_for_prompt(rubric: List[Dict[str, Any]]) -> str:
    """Format rubric criteria for the AI prompt, including criteria_id for mapping"""
    formatted = []
    
    for i, criterion in enumerate(rubric, 1):
        criteria_id = criterion.get('criteria_id', f'criterion_{i}')
        levels_text = "\n".join([
            f"    - {level['name']} ({level['points']} pts): {level.get('description', '')}"
            for level in criterion.get('levels', [])
        ])
        
        formatted.append(f"""
{i}. [ID: {criteria_id}] {criterion['name']} (Max: {criterion['points']} points)
   Description: {criterion.get('description', '')}
   Scoring Levels:
{levels_text}
""")
    
    return "\n".join(formatted)


def strip_html_tags(html_content: str) -> str:
    """Safely strip HTML tags from content to get plain text for grading.
    Does NOT use regex on untrusted input for security."""
    import html as html_module
    if not html_content:
        return ""
    # Simple tag stripping - handles common HTML from the editor
    text = html_content
    # Replace block-level tags with newlines for readability
    for tag in ['</p>', '</div>', '</h1>', '</h2>', '</h3>', '</h4>', '</h5>', '</h6>', '<br>', '<br/>', '<br />']:
        text = text.replace(tag, '\n')
    # Remove remaining tags character by character (no regex on untrusted input)
    result = []
    in_tag = False
    for ch in text:
        if ch == '<':
            in_tag = True
        elif ch == '>':
            in_tag = False
        elif not in_tag:
            result.append(ch)
    text = ''.join(result)
    # Decode HTML entities
    text = html_module.unescape(text)
    # Normalize whitespace
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(line for line in lines if line)
    return text.strip()


def extract_images_from_html(html_content: str) -> List[str]:
    """Extract base64 image data URLs from HTML content.
    Returns a list of image data URLs (up to 4 to control costs)."""
    if not html_content:
        return []
    
    images = []
    # Look for img tags with src containing base64 data
    import re
    img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
    matches = img_pattern.findall(html_content)
    
    for src in matches:
        if src.startswith('data:image/'):
            images.append(src)
        elif src.startswith('http'):
            images.append(src)
        
        # Limit to 4 images to control API costs
        if len(images) >= 4:
            break
    
    return images


async def auto_grade_submission(
    content: str,
    rubric: List[Dict[str, Any]],
    assignment_instructions: str,
    max_points: int,
    assignment_title: str = "",
    integrity_context: Optional[Dict[str, Any]] = None,
    content_html: Optional[str] = None,
    education_level: str = "university",
) -> Dict[str, Any]:
    """
    Use AI to grade a submission against a rubric, topic, and instructions.
    Supports multimodal grading (text + images) using GPT-4o vision.
    
    Args:
        content: The student's submission text
        rubric: List of rubric criteria with levels
        assignment_instructions: The assignment instructions
        max_points: Maximum points for the assignment
        assignment_title: The assignment title/topic
        integrity_context: Integrity data (trust score, stylometry, AI detection, plagiarism)
        content_html: Raw HTML content (used to extract embedded images)
        education_level: "high_school", "university", "graduate" — adjusts expectations
    
    Returns:
        Auto-grade result with scores and explanations
    """
    api_key = _get_openai_key()
    model = _get_openai_model()
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured. Set OPENAI_API_KEY in environment variables.")
    
    # Strip HTML tags to get plain text for grading (content may be HTML from the editor)
    plain_content = strip_html_tags(content) if '<' in content and '>' in content else content
    
    if not plain_content or len(plain_content.strip()) < 10:
        raise ValueError("Submission content is too short or empty for auto-grading")
    
    # Extract images from HTML content for vision-based grading
    submission_images = extract_images_from_html(content_html or content)
    
    # Truncate content if too long (to manage tokens/cost)
    max_content_length = 8000  # ~2000 words
    if len(plain_content) > max_content_length:
        plain_content = plain_content[:max_content_length] + "\n\n[Content truncated for grading...]"
    
    # Build the prompt
    rubric_text = format_rubric_for_prompt(rubric)
    
    level_expectations = {
        "high_school": "a high school student. Expect developing analytical skills, basic source integration, and simpler vocabulary. Focus on effort, comprehension of key concepts, and following instructions.",
        "university": "an undergraduate university student. Expect clear thesis statements, evidence-based arguments, proper source integration, critical analysis, and academic writing conventions.",
        "graduate": "a graduate/postgraduate student. Expect sophisticated analysis, original contribution to discourse, rigorous methodology, extensive source integration, and polished academic prose.",
    }
    level_desc = level_expectations.get(education_level, level_expectations["university"])

    system_prompt = f"""You are an expert academic grader deployed at institutions worldwide. You grade {level_desc}

CORE PRINCIPLES (non-negotiable):
1. RUBRIC IS LAW: The rubric is the sole basis for scoring. For each criterion, identify which level the submission maps to, assign that level's points, and quote evidence. Do NOT award points for criteria not demonstrated in the text.
2. EVIDENCE-OVER-IMPRESSION: Every score must cite a specific passage. If you cannot point to evidence for a criterion, the score for that criterion must reflect its absence.
3. CALIBRATED SCORING: A submission that does exactly what the rubric's middle level describes gets exactly the middle level's points — not higher, not lower. Reserve top marks for work that clearly meets the top level's description.
4. CONSTRUCTIVE FEEDBACK: For every weakness you identify, give one concrete, actionable suggestion. For every strength, explain why it works.
5. ASSIGNMENT FIDELITY: If the submission does not address the assignment prompt at all, FLAG it. Partial relevance is penalized proportionally, not flagged.

INTEGRITY AWARENESS:
- If integrity data shows high AI probability (>50%) AND stylometry mismatch, note the concern in integrity_notes but do NOT reduce rubric scores for integrity alone — that is the teacher's judgment call.
- FLAG submissions that are clearly off-topic, gibberish, or show no genuine attempt."""

    # Build integrity context section for the prompt
    integrity_section = ""
    if integrity_context:
        integrity_parts = []
        ts = integrity_context.get("trust_score", 0)
        integrity_parts.append(f"- Trust Score: {ts}%")
        
        stylometry = integrity_context.get("stylometry")
        if stylometry:
            verdict = stylometry.get("verdict", "")
            score = stylometry.get("score") or stylometry.get("similarity", 0)
            confidence = stylometry.get("confidence", "")
            status = verdict.capitalize() if verdict else "N/A"
            conf_str = f", confidence={confidence}" if confidence else ""
            integrity_parts.append(f"- Stylometry: {status} ({round(score * 100) if score else 0}% GI score{conf_str})")
        
        ai_det = integrity_context.get("ai_detection")
        if ai_det:
            ai_prob = ai_det.get("ai_probability", 0)
            integrity_parts.append(f"- AI Detection: {round(ai_prob * 100)}% probability of AI-generated content")
        
        plag = integrity_context.get("plagiarism_score", 0)
        if plag > 0:
            integrity_parts.append(f"- Plagiarism Similarity: {plag}%")
        
        if integrity_parts:
            integrity_section = "\n## INTEGRITY ANALYSIS\n" + "\n".join(integrity_parts)
            integrity_section += "\n\nIMPORTANT: Do NOT adjust rubric scores based on integrity data alone, but:"
            integrity_section += "\n- If stylometry shows MISMATCH and AI detection is HIGH (>50%), mention this concern in your overall_feedback."
            integrity_section += "\n- If the submission doesn't match the student's writing profile, flag it."
            integrity_section += "\n- Include integrity observations in the 'integrity_notes' field of your response."
    
    # Build assignment title section
    title_section = f"\n## ASSIGNMENT TITLE / TOPIC\n{assignment_title}" if assignment_title else ""

    user_prompt = f"""Grade this student submission rigorously against the provided rubric.
{title_section}

## ASSIGNMENT INSTRUCTIONS
{assignment_instructions}

## GRADING RUBRIC (use this as the sole basis for scoring)
{rubric_text}
{integrity_section}

## STUDENT SUBMISSION
{plain_content}

## EVALUATION REQUIREMENTS

### Step 1: Criterion-by-Criterion Scoring
For EACH criterion in the rubric:
- Read the criterion description and all scoring levels carefully
- Find specific evidence in the submission that maps to a scoring level
- Assign the score that BEST matches the evidence — do not round up without justification
- Write a focused 1-2 sentence explanation referencing specific content from the submission
- Quote the exact evidence used

### Step 2: Inline Annotations (Highlighted Comments)
Identify 4-8 specific passages in the student's text. For each passage:
- Select an EXACT phrase (5-30 words) from the submission — it must be a verbatim substring
- Attach a comment that is actionable and specific
- Classify as: "praise" (what works well), "suggestion" (how to improve), or "issue" (factual error, logical flaw, missing element)
- Mix of types: include at least 1 praise and 1 suggestion minimum
- Link comments to rubric criteria when relevant

### Step 3: Overall Assessment
- Sum the criterion scores for the total
- Write 2-3 sentences of holistic feedback covering strengths and the single most impactful improvement the student could make
- Rate your confidence in the assessment

Return your evaluation as a JSON object with this exact structure:
{{
    "criteria_scores": [
        {{
            "criteria_id": "<EXACT criterion ID from the [ID: ...] tag in the rubric above>",
            "criteria_name": "<criterion name>",
            "score": <number - must not exceed max_score>,
            "max_score": <number from rubric>,
            "level_name": "<name of scoring level chosen>",
            "explanation": "<1-2 sentence justification with specific reference to submission>",
            "evidence": "<exact quote from submission that supports this score>"
        }}
    ],
    "inline_annotations": [
        {{
            "highlighted_text": "<EXACT phrase from submission — must be findable via text search>",
            "comment": "<specific, actionable comment tied to rubric criteria when possible>",
            "type": "<praise|suggestion|issue>"
        }}
    ],
    "total_score": <sum of all criterion scores>,
    "max_score": {max_points},
    "overall_feedback": "<2-3 sentences: what was done well + the most important improvement needed>",
    "confidence": <0.0-1.0>,
    "flagged": <true if submission is off-topic, suspicious, or doesn't correspond to the assignment>,
    "flag_reason": "<reason for flagging, or empty string if not flagged>",
    "integrity_notes": "<observations about integrity data if concerning, or empty string>"
}}

CRITICAL RULES:
- "highlighted_text" must be an EXACT substring from the student submission text above
- Each criterion score must not exceed its max_score
- total_score = sum of all criterion scores
- Do NOT inflate grades. An average submission should receive an average score.
- If the submission is off-topic, too short, or doesn't address the assignment, score accordingly."""

    try:
        # Build user message content - multimodal if images present
        if submission_images:
            # Use vision-capable multimodal message
            user_content = [
                {"type": "text", "text": user_prompt}
            ]
            # Add images (up to 4)
            for img_url in submission_images[:4]:
                if img_url.startswith('data:image/'):
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": img_url, "detail": "low"}
                    })
                elif img_url.startswith('http'):
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": img_url, "detail": "low"}
                    })
        else:
            user_content = user_prompt
        
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.post(
            OPENAI_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.3,
                "max_tokens": 3000,
                "response_format": {"type": "json_object"}
            }
        )

        response.raise_for_status()
        result = response.json()

        # Parse the AI response
        ai_response = result["choices"][0]["message"]["content"]
        grade_data = json.loads(ai_response)

        # Validate and normalize the response - never trust AI output blindly
        criteria_scores = []
        total_score = 0

        # Build a lookup of valid criteria_ids from the rubric
        valid_criteria = {c.get('criteria_id', ''): c for c in rubric}

        for cs in grade_data.get("criteria_scores", []):
            cid = str(cs.get("criteria_id", ""))[:100]
            c_name = str(cs.get("criteria_name", "Unknown"))[:200]
            raw_score = cs.get("score", 0)
            raw_max = cs.get("max_score", 0)

            try:
                score = max(0, int(raw_score))
                c_max = max(0, int(raw_max))
            except (ValueError, TypeError):
                score = 0
                c_max = 0

            if cid in valid_criteria:
                c_max = valid_criteria[cid].get('points', c_max)

            score = min(score, c_max)

            criteria_scores.append({
                "criteria_id": cid,
                "criteria_name": c_name,
                "score": score,
                "max_score": c_max,
                "level_name": str(cs.get("level_name", ""))[:100],
                "explanation": str(cs.get("explanation", ""))[:1000],
                "evidence": str(cs.get("evidence", ""))[:500]
            })
            total_score += score

        total_score = min(total_score, max_points)

        # Parse inline annotations
        inline_annotations = []
        for ann in grade_data.get("inline_annotations", []):
            highlighted = ann.get("highlighted_text", "").strip()
            ann_type = ann.get("type", "suggestion")
            if ann_type not in ("praise", "suggestion", "issue"):
                ann_type = "suggestion"
            if highlighted and len(highlighted) >= 3 and (highlighted in plain_content or highlighted in content):
                inline_annotations.append({
                    "highlighted_text": highlighted,
                    "comment": ann.get("comment", "")[:500],
                    "type": ann_type
                })

        return {
            "total_score": total_score,
            "max_score": max_points,
            "criteria_scores": criteria_scores,
            "inline_annotations": inline_annotations,
            "overall_feedback": grade_data.get("overall_feedback", ""),
            "confidence": min(1.0, max(0.0, grade_data.get("confidence", 0.7))),
            "flagged": bool(grade_data.get("flagged", False)),
            "flag_reason": str(grade_data.get("flag_reason", ""))[:500],
            "integrity_notes": str(grade_data.get("integrity_notes", ""))[:500],
            "graded_at": datetime.now(timezone.utc).isoformat(),
            "model_used": model
        }

    except httpx.HTTPStatusError as e:
        raise ValueError(f"AI grading failed: {e.response.status_code}")
    except json.JSONDecodeError:
        raise ValueError("AI grading returned invalid response")
    except Exception as e:
        raise ValueError(f"Auto-grading failed: {str(e)}")


async def generate_feedback(
    content: str,
    grade: int,
    max_grade: int,
    criteria_scores: Optional[List[Dict]] = None,
    assignment_instructions: str = "",
    education_level: str = "university",
    assignment_title: str = "",
) -> str:
    """
    Generate constructive feedback for a submission.
    Can be used standalone or to enhance existing feedback.
    """
    api_key = _get_openai_key()
    model = _get_openai_model()

    if not api_key:
        return ""

    # Truncate content if too long
    max_content_length = 4000
    if len(content) > max_content_length:
        content = content[:max_content_length] + "\n\n[Content truncated...]"

    criteria_context = ""
    if criteria_scores:
        criteria_context = "\nRubric scores:\n" + "\n".join([
            f"- {cs['criteria_name']}: {cs['score']}/{cs['max_score']}"
            for cs in criteria_scores
        ])

    instructions_section = ""
    if assignment_instructions:
        instructions_section = f"\nASSIGNMENT INSTRUCTIONS:\n{assignment_instructions}\n"

    title_section = f' for "{assignment_title}"' if assignment_title else ""

    system_prompt = f"""You are a distinguished professor at a top-tier research university ({education_level} level).
You are providing personalized written feedback on a student submission{title_section} that received {grade}/{max_grade} points.
{instructions_section}{criteria_context}

FEEDBACK STRUCTURE (follow this exactly):

**Strengths:** Open by quoting 1-2 specific sentences from the student's work that demonstrate understanding or skill. Explain WHY these are effective.

**Areas for Improvement:** Identify 2-3 specific weaknesses. For each:
- Quote the problematic passage from their text
- Explain what's wrong and WHY it matters (relate to assignment requirements if available)
- Show what a stronger version would look like

**Next Steps:** Give 2-3 concrete, actionable items the student should do in their next revision or future work.

Rules:
- Every claim MUST reference the student's actual words — quote them directly
- When assignment instructions are provided, evaluate against those specific requirements
- Match the rigor and vocabulary expected at {education_level} level
- Be encouraging but honest — a {grade}/{max_grade} grade should be reflected in the tone
- Do NOT use generic filler ("good job", "well written", "interesting topic") without evidence
- Write in a professional academic voice, 3-4 paragraphs"""

    try:
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.post(
            OPENAI_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Student submission:\n\n{content[:3000]}"}
                ],
                "temperature": 0.5,
                "max_tokens": 900
            }
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception:
        return ""


async def detect_ai_content(content: str) -> Dict[str, Any]:
    """
    Use AI to detect potentially AI-generated content.
    This is a supplementary check to GPTZero.
    
    Note: This is less accurate than dedicated services like GPTZero
    but can provide additional signals.
    """
    api_key = _get_openai_key()
    model = _get_openai_model()
    
    if not api_key:
        return {"ai_probability": 0, "status": "api_key_missing"}
    
    # Truncate content
    max_content_length = 4000
    if len(content) > max_content_length:
        content = content[:max_content_length]
    
    prompt = f"""Analyze this text and estimate the probability it was written by an AI language model vs a human student.

Consider these factors:
- Writing style consistency
- Use of filler phrases common in AI text
- Vocabulary diversity
- Natural vs artificial transitions
- Presence of personal experiences or opinions
- Specificity of examples

Text to analyze:
{content}

Respond with a JSON object:
{{
    "ai_probability": <0.0-1.0>,
    "human_probability": <0.0-1.0>,
    "confidence": <0.0-1.0>,
    "indicators": ["list of specific indicators you noticed"],
    "assessment": "<brief explanation>"
}}"""

    try:
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.post(
            OPENAI_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
                "response_format": {"type": "json_object"}
            }
        )
        response.raise_for_status()
        result = response.json()
        ai_response = json.loads(result["choices"][0]["message"]["content"])
        return {
            "ai_probability": ai_response.get("ai_probability", 0),
            "human_probability": ai_response.get("human_probability", 1),
            "confidence": ai_response.get("confidence", 0.5),
            "indicators": ai_response.get("indicators", []),
            "assessment": ai_response.get("assessment", ""),
            "status": "success"
        }
    except Exception as e:
        return {
            "ai_probability": 0,
            "status": "error",
            "message": str(e)
        }
