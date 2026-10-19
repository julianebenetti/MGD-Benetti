"""
Video Processor
Processa vídeos com FFmpeg: redimensiona, ajusta proporção e adiciona marca d'água
"""

import logging
import subprocess
import os
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_LOGO = Path(__file__).parent / 'assets' / 'logo_achados_relampagos.png'
# Proporções medidas no print de referência do app Shopee Video
LOGO_WIDTH_RATIO = 0.25
# Em tela cheia o app corta ~9% de cada lateral (celular 19,5:9 x vídeo 9:16): o logo fica fora desse corte
# e abaixo da seta de voltar/barra de busca
LOGO_MARGIN_X_RATIO = 0.11
LOGO_TOP_RATIO = 0.12


class VideoProcessor:
    def __init__(self, aspect_ratio: str = '9:16', width: int = 1080,
                 height: int = 1920, bitrate: str = '5M', fps: int = 30):
        self.aspect_ratio = aspect_ratio
        self.width = width
        self.height = height
        self.bitrate = bitrate
        self.fps = fps

        # Verificar se ffmpeg está instalado
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Verifica se FFmpeg está instalado"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            logger.info("✅ FFmpeg encontrado")
        except FileNotFoundError:
            logger.error("❌ FFmpeg não encontrado. Instale com: apt-get install ffmpeg")
            raise

    def process(self, input_video: str, output_dir: Path) -> Optional[str]:
        """
        Processa vídeo para 9:16 (1920x1080 em proporção 9:16)
        - Redimensiona
        - Ajusta proporção (adiciona bordas pretas se necessário)
        - Comprime com bitrate apropriado
        """
        try:
            output_file = output_dir / f"processed_{Path(input_video).stem}.mp4"

            logger.info(f"Processando: {input_video}")
            logger.info(f"Saída: {output_file}")

            # FFmpeg comando para:
            # 1. Escalar para altura 1920 mantendo proporção
            # 2. Padding para 1080x1920 (9:16)
            # 3. Comprimir com bitrate apropriado
            # 4. 30 FPS

            cmd = [
                'ffmpeg',
                '-i', input_video,
                '-vf', f"""
                    scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,
                    pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color=black
                """.replace('\n', '').replace('  ', ''),
                '-r', str(self.fps),
                '-b:v', self.bitrate,
                '-c:v', 'libx264',
                '-crf', '23',
                '-preset', 'medium',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                str(output_file)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Erro FFmpeg: {result.stderr}")
                return None

            logger.info(f"✅ Vídeo processado: {output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"Erro ao processar vídeo: {e}")
            return None

    def render(self, input_video: str, output_dir: Path, cta_path: Optional[str] = None,
               cta_seconds: float = 5.0, logo_path: str = str(DEFAULT_LOGO)) -> Optional[Tuple[str, str]]:
        """
        Uma passada só: o vídeo 9:16 limpo (para os quadros da capa, codificação rápida) e o final
        com logo e CTA nos `cta_seconds` finais (mesma qualidade de antes, sem recodificar duas vezes).
        """
        stem = Path(input_video).stem
        clean = output_dir / f"processed_{stem}.mp4"
        final = output_dir / f"watermarked_processed_{stem}.mp4"
        logo_w = int(self.width * LOGO_WIDTH_RATIO)
        margin_x = int(self.width * LOGO_MARGIN_X_RATIO)
        margin_y = int(self.height * LOGO_TOP_RATIO)
        graph = (f"[0:v]scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
                 f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color=black,fps={self.fps},"
                 f"split=2[clean][w0];[1:v]scale={logo_w}:-1[logo];[w0][logo]overlay={margin_x}:{margin_y}")
        inputs = ['-i', input_video, '-i', logo_path]
        if cta_path:
            start = max(0.0, self.get_video_info(input_video).get('duration', 0) - cta_seconds)
            inputs += ['-i', cta_path]
            graph += f"[w1];[w1][2:v]overlay=0:0:enable='gte(t,{start:.2f})'"
        graph += "[final]"
        audio = ['-map', '0:a?', '-c:a', 'aac', '-b:a', '128k']
        cmd = ['ffmpeg', '-loglevel', 'error', *inputs, '-filter_complex', graph,
               '-map', '[clean]', *audio, '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-y', str(clean),
               '-map', '[final]', *audio, '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-y', str(final)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Erro FFmpeg: {result.stderr}")
            return None
        logger.info(f"✅ Vídeo pronto: {final}")
        return str(clean), str(final)

    def add_watermark(self, video_path: str, logo_path: str = str(DEFAULT_LOGO),
                      output_dir: Optional[Path] = None, cta_path: Optional[str] = None,
                      cta_seconds: float = 5.0) -> Optional[str]:
        """
        Sobrepõe o logo no canto superior esquerdo (abaixo da barra de busca da Shopee) e,
        se houver, a imagem da CTA nos `cta_seconds` finais.
        """
        try:
            if output_dir is None:
                output_dir = Path(video_path).parent

            output_file = output_dir / f"watermarked_{Path(video_path).stem}.mp4"

            logger.info(f"Adicionando logo: {logo_path}")

            logo_w = int(self.width * LOGO_WIDTH_RATIO)
            margin_x = int(self.width * LOGO_MARGIN_X_RATIO)
            margin_y = int(self.height * LOGO_TOP_RATIO)

            graph = f"[1:v]scale={logo_w}:-1[logo];[0:v][logo]overlay={margin_x}:{margin_y}"
            inputs = ['-i', video_path, '-i', logo_path]
            if cta_path:
                start = max(0.0, self.get_video_info(video_path).get('duration', 0) - cta_seconds)
                inputs += ['-i', cta_path]
                graph += f"[v];[v][2:v]overlay=0:0:enable='gte(t,{start:.2f})'"
            cmd = [
                'ffmpeg',
                *inputs,
                '-filter_complex', graph,
                '-c:v', 'libx264',
                '-crf', '23',
                '-preset', 'medium',
                '-c:a', 'copy',
                '-y',
                str(output_file)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Erro ao adicionar marca d'água: {result.stderr}")
                return None

            logger.info(f"✅ Marca d'água adicionada: {output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"Erro ao adicionar marca d'água: {e}")
            return None

    def prepend_cover(self, cover_path: str, video_path: str, output_path: str,
                      seconds: float = 1.0) -> Optional[str]:
        """Vídeo final: a capa parada por `seconds` na abertura, seguida do vídeo."""
        try:
            has_audio = bool(subprocess.run(
                ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index',
                 '-of', 'csv=p=0', video_path], capture_output=True, text=True).stdout.strip())
            size = f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease," \
                   f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={self.fps},format=yuv420p"
            cmd = ['ffmpeg', '-loglevel', 'error', '-loop', '1', '-t', str(seconds), '-i', cover_path,
                   '-i', video_path]
            if has_audio:
                cmd += ['-f', 'lavfi', '-t', str(seconds), '-i', 'anullsrc=r=44100:cl=stereo',
                        '-filter_complex',
                        f"[0:v]{size}[c];[1:v]{size}[v];[1:a]aresample=44100[a];"
                        f"[c][2:a][v][a]concat=n=2:v=1:a=1[outv][outa]",
                        '-map', '[outv]', '-map', '[outa]', '-c:a', 'aac', '-b:a', '128k']
            else:
                cmd += ['-filter_complex', f"[0:v]{size}[c];[1:v]{size}[v];[c][v]concat=n=2:v=1:a=0[outv]",
                        '-map', '[outv]']
            cmd += ['-c:v', 'libx264', '-crf', '23', '-preset', 'medium', '-movflags', '+faststart',
                    '-y', output_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Erro ao juntar capa e vídeo: {result.stderr}")
                return None
            logger.info(f"✅ Capa adicionada na abertura: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Erro ao juntar capa e vídeo: {e}")
            return None

    def get_video_info(self, video_path: str) -> dict:
        """Extrai informações do vídeo (duração, resolução, etc)"""
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                   '-of', 'json', video_path]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            data = json.loads(result.stdout)

            video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), {})

            return {
                'duration': float(data['format'].get('duration', 0)),
                'width': video_stream.get('width', 0),
                'height': video_stream.get('height', 0),
                'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                'size_mb': float(data['format'].get('size', 0)) / (1024 * 1024)
            }

        except Exception as e:
            logger.error(f"Erro ao obter informações do vídeo: {e}")
            return {}
