import os
import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate-graph", tags=["generate-graph"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class GraphRequest(BaseModel):
    text: str


@router.post("")
async def generate_graph(req: GraphRequest):
    """
    Parse user input (math expression, equation name, verbal description)
    into function-plot compatible config for interactive client-side rendering.
    """
    try:
        resp = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a math function parser. Given user input, return a JSON object for the function-plot library.\n"
                        "The JSON MUST have this exact structure:\n"
                        "{\n"
                        '  "title": "Descriptive Graph Title",\n'
                        '  "description": "1-2 sentence explanation of what the graph shows and why it matters",\n'
                        '  "xLabel": "x-axis label with units if applicable (e.g. Time (s), x)",\n'
                        '  "yLabel": "y-axis label with units if applicable (e.g. Velocity (m/s), f(x))",\n'
                        '  "functions": [\n'
                        '    { "fn": "x^2", "color": "#4F46E5", "label": "f(x) = x²" },\n'
                        '    { "fn": "sin(x)", "color": "#EC4899", "label": "g(x) = sin(x)" }\n'
                        "  ],\n"
                        '  "xDomain": [-10, 10],\n'
                        '  "yDomain": [-10, 10],\n'
                        '  "annotations": [\n'
                        '    { "x": 0, "text": "Origin" }\n'
                        "  ]\n"
                        "}\n\n"
                        "RULES:\n"
                        "- fn strings must use function-plot syntax: x^2, sin(x), cos(x), tan(x), log(x), sqrt(x), abs(x), exp(x), etc.\n"
                        "- For fractions use: 1/x, (x+1)/(x-1)\n"
                        "- For constants: pi, e\n"
                        "- label: use clean math notation with Unicode symbols like ², ³, etc.\n"
                        "- Multiple functions are allowed if user asks to compare or plot multiple.\n"
                        "- Choose good xDomain/yDomain to show the interesting parts of the graph. Add ~20% padding.\n"
                        "- Use these colors in order: #4F46E5 (indigo), #EC4899 (pink), #10B981 (emerald), #F59E0B (amber), #EF4444 (red), #8B5CF6 (purple).\n"
                        "- xLabel/yLabel should be meaningful: for physics use proper units, for math use f(x)/g(x)/y.\n"
                        "- annotations: mark key points like roots, maxima, minima, intersections, asymptotes. Max 4 annotations. Can be empty array [].\n"
                        "- description: explain the graph in plain English for students. Mention key properties.\n"
                        "- If user says a physics law or named equation, pick the most common mathematical form and explain in description.\n"
                        "- Return ONLY valid JSON, no markdown, no explanation.\n"
                    ),
                },
                {"role": "user", "content": req.text},
            ],
            temperature=0.0,
        )

        raw = resp.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        config = json.loads(raw)

        # Validate structure
        if "functions" not in config or not isinstance(config["functions"], list):
            raise ValueError("Missing or invalid 'functions' array")

        return config

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Graph config parse error: {e}, raw: {raw}")
        raise HTTPException(status_code=422, detail=f"Failed to parse graph config: {e}")
    except OpenAIError as e:
        logger.error(f"OpenAI API error in generate-graph: {e}")
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {e}")
