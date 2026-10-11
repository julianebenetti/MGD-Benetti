"""
Chamada única à Claude com resposta em JSON garantida por esquema.
"""

import json
import logging
from typing import Dict, List, Union

import anthropic

logger = logging.getLogger(__name__)

MODEL = 'claude-opus-5-5'
_client = None


class ClaudeRefusal(RuntimeError):
    pass


def ask_json(content: Union[str, List[Dict]], schema: Dict, max_tokens: int = 4000,
             effort: str = 'medium') -> Dict:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()

    response = _client.beta.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        betas=['server-side-fallback-2026-07-01'],
        fallbacks='default',
        output_config={'effort': effort, 'format': {'type': 'json_schema', 'schema': schema}},
        messages=[{'role': 'user', 'content': content}],
    )
    if response.stop_reason == 'refusal':
        raise ClaudeRefusal(getattr(response.stop_details, 'explanation', None) or 'recusado')
    text = next(b.text for b in response.content if b.type == 'text')
    return json.loads(text)
