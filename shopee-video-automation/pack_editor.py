"""
📦 Pack de vídeos (pedido de 15/11): o pack manda, para cada produto, 5 vídeos de ~8 s, 5 vinhetas de ~4 s e 5
imagens. O robô junta cada vídeo com a vinheta de OUTRO vídeo do pack (sorteio sem repetir o par "natural"),
alternando a vinheta antes ou depois, para o vídeo dela não ficar igual ao das outras pessoas que compraram o pack.
O produto não é espelhado nem alterado (isso daria "produto irrelevante").
"""

import json
import os
import logging
import random
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

MAIN_MIN_SECONDS = 6.0   # a partir disso é "vídeo"; abaixo, "vinheta/complemento"
FADE_SECONDS = float(os.getenv('PACK_TRANSICAO', '0.5'))   # duração da transição suave entre vídeo e vinheta


def probe(path: str) -> Dict:
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height:format=duration',
                          '-of', 'json', path], capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    video = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), {})
    return {'duration': float(data.get('format', {}).get('duration') or 0),
            'width': int(video.get('width') or 1080), 'height': int(video.get('height') or 1920),
            'audio': any(s.get('codec_type') == 'audio' for s in data.get('streams', []))}


def pairs(n_main: int, n_extra: int, rng: random.Random) -> List[Tuple[int, int, bool]]:
    """
    (vídeo, vinheta, vinheta_antes) para cada vídeo: a vinheta sorteada nunca é a de mesmo número (quando há mais de
    uma), e a posição alterna (antes/depois) começando por um lado sorteado.
    """
    if not n_extra:
        return [(i, -1, False) for i in range(n_main)]
    order = list(range(n_extra))
    for _ in range(50):
        rng.shuffle(order)
        if n_extra == 1 or all(order[i % n_extra] != i for i in range(min(n_main, n_extra))):
            break
    first = rng.random() < 0.5
    return [(i, order[i % n_extra], (i % 2 == 0) == first) for i in range(n_main)]


def join(main: str, extra: str, before: bool, out: str) -> str:
    """Junta vídeo + vinheta (vinheta antes ou depois), no tamanho do vídeo principal, 30 fps, áudio estéreo."""
    a, b = (extra, main) if before else (main, extra)
    pa, pb, pm = probe(a), probe(b), probe(main)
    w, h = pm['width'] // 2 * 2, pm['height'] // 2 * 2
    args = ['ffmpeg', '-y', '-loglevel', 'error', '-i', a, '-i', b]
    for info in (pa, pb):
        if not info['audio']:   # sem áudio: entra um silêncio do mesmo tamanho (entradas 2 e 3, nesta ordem)
            args += ['-f', 'lavfi', '-t', f"{info['duration']:.3f}", '-i', 'anullsrc=r=44100:cl=stereo']
    silent = 2
    audio = []
    for idx, info in ((0, pa), (1, pb)):
        if info['audio']:
            audio.append(f'[{idx}:a]')
        else:
            audio.append(f'[{silent}:a]')
            silent += 1
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
          f"setsar=1,fps=30,format=yuv420p")
    af = 'aresample=44100,aformat=channel_layouts=stereo'
    # transição suave (dissolve) entre as duas partes, sem cortar o produto
    fade = min(FADE_SECONDS, pa['duration'] / 3, pb['duration'] / 3)
    offset = max(pa['duration'] - fade, 0.1)
    graph = (f"[0:v]{vf}[v0];[1:v]{vf}[v1];{audio[0]}{af}[a0];{audio[1]}{af}[a1];"
             f"[v0][v1]xfade=transition=fade:duration={fade:.2f}:offset={offset:.2f}[v];"
             f"[a0][a1]acrossfade=d={fade:.2f}[a]")
    args += ['-filter_complex', graph, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast',
             '-crf', '20', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', out]
    subprocess.run(args, check=True, capture_output=True)
    return out


def build(mains: List[str], extras: List[str], folder: Path, seed: int) -> List[Dict]:
    """Os vídeos montados: [{'path', 'main', 'extra', 'before'}] (índices a partir de 1)."""
    folder.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    out = []
    for i, j, before in pairs(len(mains), len(extras), rng):
        target = str(folder / f"pack_{seed}_{i + 1}.mp4")
        if j < 0:
            Path(target).write_bytes(Path(mains[i]).read_bytes())
        else:
            join(mains[i], extras[j], before, target)
        out.append({'path': target, 'main': i + 1, 'extra': j + 1 if j >= 0 else 0, 'before': before})
    return out
