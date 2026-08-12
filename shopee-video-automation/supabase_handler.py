"""
Supabase Handler
Armazena rascunhos e histórico de vídeos processados
"""

import logging
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseHandler:
    def __init__(self):
        self.url = os.getenv('SUPABASE_URL')
        self.key = os.getenv('SUPABASE_KEY')

        if not self.url or not self.key:
            logger.warning("Supabase não configurado - dados não serão armazenados")
            self.client = None
            return

        try:
            self.client: Client = create_client(self.url, self.key)
            logger.info("✅ Conectado ao Supabase")
        except Exception as e:
            logger.error(f"Erro ao conectar Supabase: {e}")
            self.client = None

    def save_draft(self, draft_data: Dict) -> bool:
        """Salva rascunho no Supabase"""
        if not self.client:
            logger.warning("Supabase não disponível - salvando localmente")
            return self._save_local(draft_data)

        try:
            data = {
                'video_path': draft_data['video_path'],
                'product_url': draft_data['product_url'],
                'product_info': json.dumps(draft_data['product_info']),
                'metadata': json.dumps(draft_data['metadata']),
                'status': 'draft',
                'created_at': datetime.now().isoformat(),
                'processed': False
            }

            response = self.client.table('shopee_video_drafts').insert(data).execute()

            logger.info(f"✅ Rascunho salvo no Supabase: {response.data[0]['id']}")
            return True

        except Exception as e:
            logger.error(f"Erro ao salvar rascunho: {e}")
            return False

    def get_drafts(self, status: str = 'draft') -> List[Dict]:
        """Busca rascunhos por status"""
        if not self.client:
            return []

        try:
            response = self.client.table('shopee_video_drafts').select(
                '*'
            ).eq('status', status).order(
                'created_at', desc=True
            ).execute()

            return response.data or []

        except Exception as e:
            logger.error(f"Erro ao buscar rascunhos: {e}")
            return []

    def update_draft(self, draft_id: int, status: str, notes: Optional[str] = None) -> bool:
        """Atualiza status de um rascunho"""
        if not self.client:
            return False

        try:
            data = {
                'status': status,
                'updated_at': datetime.now().isoformat()
            }

            if notes:
                data['notes'] = notes

            self.client.table('shopee_video_drafts').update(data).eq('id', draft_id).execute()
            logger.info(f"✅ Rascunho {draft_id} atualizado: {status}")
            return True

        except Exception as e:
            logger.error(f"Erro ao atualizar rascunho: {e}")
            return False

    def log_processing(self, video_path: str, status: str, error: Optional[str] = None) -> bool:
        """Registra log de processamento"""
        if not self.client:
            return False

        try:
            data = {
                'video_path': video_path,
                'status': status,
                'error': error,
                'timestamp': datetime.now().isoformat()
            }

            self.client.table('processing_logs').insert(data).execute()
            return True

        except Exception as e:
            logger.error(f"Erro ao registrar log: {e}")
            return False

    @staticmethod
    def _save_local(draft_data: Dict) -> bool:
        """Fallback: salva em arquivo JSON local"""
        try:
            drafts_dir = 'drafts'
            os.makedirs(drafts_dir, exist_ok=True)

            filename = f"draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(drafts_dir, filename)

            with open(filepath, 'w') as f:
                json.dump(draft_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Rascunho salvo localmente: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erro ao salvar localmente: {e}")
            return False


# SQL Migration para criar as tabelas no Supabase
SUPABASE_MIGRATION = """
-- Tabela de rascunhos de vídeos
CREATE TABLE shopee_video_drafts (
    id BIGSERIAL PRIMARY KEY,
    video_path TEXT NOT NULL,
    product_url TEXT NOT NULL,
    product_info JSONB,
    metadata JSONB,
    status VARCHAR(20) DEFAULT 'draft', -- draft, published, error
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);

-- Tabela de logs de processamento
CREATE TABLE processing_logs (
    id BIGSERIAL PRIMARY KEY,
    video_path TEXT NOT NULL,
    status VARCHAR(20),
    error TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para performance
CREATE INDEX idx_drafts_status ON shopee_video_drafts(status);
CREATE INDEX idx_drafts_created ON shopee_video_drafts(created_at DESC);
CREATE INDEX idx_logs_timestamp ON processing_logs(timestamp DESC);

-- RLS (Row Level Security) - opcional
ALTER TABLE shopee_video_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_logs ENABLE ROW LEVEL SECURITY;
"""
