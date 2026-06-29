"""
Camada de Dados — Elite Rodas Assinaturas MVP (Cloud).
Gerencia PostgreSQL e Supabase Storage para contratos e auditoria jurídica.
"""

import os
import tempfile
import uuid
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

import streamlit as st
from supabase import Client, create_client

BUCKET_NAME = "contratos_pdf"
TEMP_DIR = os.path.join(tempfile.gettempdir(), "elite_rodas_cache")


class DatabaseHandler:
    """Handler centralizado para persistência em Supabase (DB + Storage)."""

    def __init__(self) -> None:
        os.makedirs(TEMP_DIR, exist_ok=True)
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        self.supabase: Client = create_client(url, key)

    def upload_pdf(self, caminho_local: str, nome_arquivo_destino: str) -> None:
        """
        Envia um PDF local para o bucket contratos_pdf no Supabase Storage.

        Raises:
            FileNotFoundError: Se o arquivo local não existir.
            RuntimeError: Em falha no upload.
        """
        if not os.path.exists(caminho_local):
            raise FileNotFoundError(f"Arquivo local não encontrado: {caminho_local}")

        try:
            with open(caminho_local, "rb") as arquivo:
                self.supabase.storage.from_(BUCKET_NAME).upload(
                    nome_arquivo_destino,
                    arquivo,
                    file_options={"content-type": "application/pdf", "upsert": "true"},
                )
        except Exception as exc:
            raise RuntimeError(f"Falha no upload do PDF: {exc}") from exc

    def download_pdf(self, nome_arquivo: str, caminho_local_destino: str) -> None:
        """
        Baixa um PDF do Supabase Storage para um caminho local temporário.

        Raises:
            RuntimeError: Em falha no download.
        """
        try:
            dados = self.supabase.storage.from_(BUCKET_NAME).download(nome_arquivo)
            os.makedirs(os.path.dirname(caminho_local_destino), exist_ok=True)
            with open(caminho_local_destino, "wb") as destino:
                destino.write(dados)
        except Exception as exc:
            raise RuntimeError(f"Falha no download do PDF: {exc}") from exc

    def criar_contrato(self, nome: str, telefone: str, modelo: str) -> str:
        """
        Gera um token UUID único e persiste os dados iniciais do contrato.

        O nome do arquivo no Storage segue o padrão {token}_original.pdf.

        Raises:
            RuntimeError: Em falha de escrita no banco.
        """
        token = str(uuid.uuid4())
        data_criacao = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        nome_arquivo_storage = f"{token}_original.pdf"

        try:
            self.supabase.table("contratos").insert(
                {
                    "token_uuid": token,
                    "cliente_nome": nome,
                    "cliente_telefone": telefone,
                    "modelo_scooter": modelo,
                    "data_criacao": data_criacao,
                    "status": "Pendente",
                    "caminho_pdf_original": nome_arquivo_storage,
                }
            ).execute()
        except Exception as exc:
            raise RuntimeError(f"Falha ao criar contrato: {exc}") from exc

        return token

    def buscar_contrato(self, token: str) -> Optional[Dict[str, str]]:
        """
        Busca os dados de um contrato pelo token.

        Returns:
            Dict com nome, modelo, status e caminho_pdf_original, ou None.
        """
        try:
            resposta = (
                self.supabase.table("contratos")
                .select("cliente_nome, modelo_scooter, status, caminho_pdf_original")
                .eq("token_uuid", token)
                .execute()
            )
        except Exception as exc:
            raise RuntimeError(f"Falha ao buscar contrato: {exc}") from exc

        if not resposta.data:
            return None

        registro = resposta.data[0]
        return {
            "nome": registro["cliente_nome"],
            "modelo": registro["modelo_scooter"],
            "status": registro["status"],
            "caminho_pdf_original": registro.get("caminho_pdf_original") or "",
        }

    def registrar_assinatura(
        self,
        token: str,
        ip: str,
        user_agent: str,
        hash_doc: str,
    ) -> None:
        """
        Atualiza o status do contrato para 'Assinado' e grava log de auditoria.

        Raises:
            ValueError: Se o contrato não existir ou já estiver assinado.
            RuntimeError: Em falha de escrita no banco.
        """
        contrato = self.buscar_contrato(token)
        if contrato is None:
            raise ValueError("Contrato não encontrado.")
        if contrato["status"] == "Assinado":
            raise ValueError("Este contrato já foi assinado.")

        data_assinatura = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        try:
            self.supabase.table("contratos").update({"status": "Assinado"}).eq(
                "token_uuid", token
            ).execute()

            self.supabase.table("auditoria").insert(
                {
                    "token_uuid": token,
                    "data_assinatura": data_assinatura,
                    "ip_cliente": ip,
                    "user_agent": user_agent,
                    "hash_documento": hash_doc,
                }
            ).execute()
        except Exception as exc:
            raise RuntimeError(f"Falha ao registrar assinatura: {exc}") from exc
