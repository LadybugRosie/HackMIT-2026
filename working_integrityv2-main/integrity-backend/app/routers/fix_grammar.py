import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fix-grammar", tags=["fix-grammar"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class GrammarRequest(BaseModel):
    text: str


@router.post("")
async def fix_grammar(req: GrammarRequest):
    """
    Fix only grammar, spelling, and punctuation errors.
    Does NOT rephrase, rewrite, or change the meaning/style.
    """
    try:
        resp = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a grammar-only corrector. "
                        "Fix ONLY grammar, spelling, and punctuation errors. "
                        "Do NOT rephrase, reword, restructure, or change the tone, style, or meaning. "
                        "Keep the original words, sentence structure, and voice exactly as they are. "
                        "If a sentence is grammatically correct, return it unchanged. "
                        "Return ONLY the corrected text with no explanations, no quotes, no extra formatting."
                    ),
                },
                {"role": "user", "content": req.text},
            ],
            temperature=0.0,
        )

        corrected = resp.choices[0].message.content.strip()
        return {"corrected_text": corrected}

    except OpenAIError as e:
        logger.error(f"OpenAI API error in fix-grammar: {e}")
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {e}")
