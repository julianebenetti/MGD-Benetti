"""
Video Processor
Processa vídeos com FFmpeg: redimensiona, ajusta proporção e adiciona marca d'água
"""

import logging
import subprocess
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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

    def add_watermark(self, video_path: str, text: str = "AfiliDash",
                     output_dir: Optional[Path] = None) -> Optional[str]:
        """Adiciona marca d'água ao vídeo"""
        try:
            if output_dir is None:
                output_dir = Path(video_path).parent

            output_file = output_dir / f"watermarked_{Path(video_path).stem}.mp4"

            logger.info(f"Adicionando marca d'água: {text}")

            # FFmpeg comando para adicionar texto
            # Posiciona no canto inferior direito
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vf', f"""
                    drawtext=
                    text='{text}':
                    fontsize=40:
                    fontcolor=white:
                    x=w-tw-20:
                    y=h-th-20:
                    box=1:
                    boxcolor=black@0.5:
                    boxborderw=5
                """.replace('\n', '').replace('  ', ''),
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
