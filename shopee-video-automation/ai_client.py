"""
Chamada única à OpenAI com resposta em JSON garantida por esquema (structured outputs).
"""

import json
import logging
import os
from typing import Dict, List, Union

from openai import OpenAI

logger = logging.getLogger(__name__)

_client = None


def _http_client():
    """Conexão só por IPv4 (VPS com IPv6 quebrado deixava cada chamada pendurada); FORCAR_IPV4=nao desliga."""
    import httpx2
    from openai import DefaultHttpxClient
    if os.getenv('FORCAR_IPV4', 'sim').strip().lower() == 'nao':
        return DefaultHttpxClient()
    return DefaultHttpxClient(transport=httpx2.HTTPTransport(local_address='0.0.0.0'))


class AIRefusal(RuntimeError):
    pass


def _to_openai(block: Dict) -> Dict:
    if block['type'] == 'image':
        src = block['source']
        return {'type': 'image_url',
                'image_url': {'url': f"data:{src['media_type']};base64,{src['data']}"}}
    return {'type': 'text', 'text': block['text']}


def ask_json(content: Union[str, List[Dict]], schema: Dict, name: str = 'resposta') -> Dict:
    """`content`: texto, ou lista de blocos {'type': 'text'|'image', ...} (imagem em base64)."""
    global _client
    if _client is None:
        _client = OpenAI(http_client=_http_client())

    if not isinstance(content, str):
        content = [_to_openai(b) for b in content]
    response = _client.chat.completions.create(
        model=os.getenv('OPENAI_MODEL', 'gpt-5.6-luna'),
        messages=[{'role': 'user', 'content': content}],
        response_format={'type': 'json_schema',
                         'json_schema': {'name': name, 'strict': True, 'schema': schema}},
    )
    message = response.choices[0].message
    if message.refusal:
        raise AIRefusal(message.refusal)
    return json.loads(message.content)
