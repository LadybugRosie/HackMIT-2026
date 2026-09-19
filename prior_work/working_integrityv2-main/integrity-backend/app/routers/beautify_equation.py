import re
import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/beautify-equation", tags=["beautify-equation"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class BeautifyRequest(BaseModel):
    text: str


@router.post("")
async def beautify_equation(req: BeautifyRequest):
    """
    Takes user input (broken math, verbal formula, etc.) and returns clean
    LaTeX that the tiptap math extension can parse.
    """
    prompt = (
        "Convert the following user input—whether it's a broken equation, "
        "a verbal description of a formula, or the name of a law—into clean, "
        "KaTeX-ready LaTeX math code. "
        "Return ONLY the LaTeX code (no JSON, no extra text).\n\n"
        "The supported formats are"
        " $\\sin(x)$, $\\cos(x)$, $\\tan(x)$, $\\log(x)$, $\\ln(x)$, $\\sqrt{x}$, $\\frac{a}{b}$, $x^2$, $x^3$, $e^x$, $\\sum_{i=0}^n x_i$, $\\int_a^b x^2 dx$,$\\frac{1}{x}$,$\\binom{n}{k}$,$\\left(\\frac{1}{x}\\right)$, $\\left\\{\\begin{matrix}x&\\text{if }x>0\\\\0&\\text{otherwise}\\end{matrix}\\right.$  ."
        "So always return the latex code in above format.\n\n"
        f"{req.text}"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": "You are a converter from plain math to tiptap math extension parsing latex format."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )

        latex = resp.choices[0].message.content.strip()
        latex = re.sub(r"\\frac", r"\\dfrac", latex)
        return f"$$\n{latex}\n$$"

    except OpenAIError as e:
        logger.error(f"OpenAI API error in beautify-equation: {e}")
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {e}")
