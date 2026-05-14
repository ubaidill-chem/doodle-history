import json

from google import genai


CLEANUP_PROMPT = """You are reviewing a universe of historical concepts for a 20th century history discovery game. The game models history through material conditions, economics, and power structures.

## Universe ({n} items)
{current_universe}

## Task
For each item, flag ONE of the following if applicable:

GRANULARITY: Item is too specific to be a meaningful combination node —
it is a consequence or sub-event of another item in the universe rather
than a concept that can independently produce or be produced by multiple others.
Provide the parent item it should instead be flavor text on.

DUPLICATE: Item overlaps significantly in meaning with another item in
the universe such that players would not experience them as distinct.
Provide the item it duplicates.

TYPO: Item contains a spelling or capitalization error.
Provide the correction.

If an item has none of these issues, omit it from the output entirely.

Output: JSON only. No commentary."""


CLEANUP_SCHEMA = {
  "type": "object",
  "properties": {
    "flags": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "item": {
            "type": "string"
          },
          "issue": {
            "type": "string",
            "enum": ["granularity", "duplicate", "typo"]
          },
          "reason": {
            "type": "string"
          },
          "action": {
            "type": "string"
          }
        },
        "required": ["item", "issue", "reason", "action"],
        "additionalProperties": False
      }
    }
  },
  "required": ["flags"],
  "additionalProperties": False
}


EXPANSION_PROMPT_V2 = """You are extending a universe of historical concepts for a 20th century history discovery game. The game models history through material conditions, economics, and power structures.

## Current universe ({n} items)
{current_universe}

## Task
Identify concepts that are:
1. NOT already in the universe (check carefully before suggesting)
2. Producible by combining 2-3 items already in the universe in a specific, coherent manner consistent with the materialist lens of the game
3. Themselves able to produce further items — not terminal facts
4. At concept granularity, not event granularity
   YES: "Famine", "Censorship", "Inflation", "Class Struggle"
   NO: "Crop Failure in Ukraine 1932", "Burning of Books", "1970s Oil Prices"
5. High betweenness — bridges multiple thematic clusters rather than extending one cluster deeper

For each candidate, name the two clusters it bridges.
Return 10-20 candidates. If fewer than 5 genuinely missing concepts exist,
say so — do not pad with weak suggestions.

Output: JSON only."""

EXPANSION_SCHEMA = {
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "bridges": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "minItems": 2,
            "maxItems": 2,
            "description": "Exactly two cluster names that this item connects."
          },
          "example_combination": {
            "type": "string",
            "description": "Example format: 'Item X + Item Y --> this concept'"
          }
        },
        "required": ["name", "bridges", "example_combination"],
        "additionalProperties": False
      }
    },
    "saturation_note": {
      "type": "string"
    }
  },
  "required": ["items", "saturation_note"],
  "additionalProperties": False
}


CLIENT = genai.Client()


def cleanup(elems: list[str]):
    response = CLIENT.models.generate_content(
        model='gemini-3-flash-preview',
        contents=CLEANUP_PROMPT.format(n=len(elems), current_universe=', '.join(elems)),
        config={
                "response_mime_type": "application/json",
                "response_json_schema": CLEANUP_SCHEMA
            }
    )
    with open('cleanup.json', 'w', encoding='utf-8') as f:
        json.dump(response.parsed, f) # type: ignore


def expand(elems: list[str]):
    response = CLIENT.models.generate_content(
        model='gemini-3-flash-preview',
        contents=EXPANSION_PROMPT_V2.format(n=len(elems), current_universe=', '.join(elems)),
        config={
                "response_mime_type": "application/json",
                "response_json_schema": EXPANSION_SCHEMA
            }
    )
    res: dict = response.parsed # type: ignore
    with open('expansion.json', 'w', encoding='utf-8') as f:
        json.dump(res, f)
    
    with open("data.csv", 'a', encoding='utf-8') as f:
        f.write(','.join([a['name'] for a in res['items']]))
    

with open("data.csv", 'r', encoding='utf-8') as f:
    elems = [x for line in f.readlines() for x in line.strip('\n').split(',') if x]

expand(elems)
