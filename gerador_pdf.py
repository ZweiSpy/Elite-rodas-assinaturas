"""
Camada de Documentos — Elite Rodas Assinaturas MVP.
Mescla o PDF original do vendedor com página de assinatura e auditoria jurídica.
"""

import hashlib
import os
from typing import Dict

from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

from database import TEMP_DIR


class GeradorContrato:
    """Responsável pela página de auditoria, mesclagem de PDFs e hash de integridade."""

    @staticmethod
    def gerar_hash_seguranca(texto_base: str) -> str:
        """Gera hash SHA-256 a partir de uma string."""
        return hashlib.sha256(texto_base.encode("utf-8")).hexdigest()

    @staticmethod
    def gerar_hash_arquivo(caminho_arquivo: str) -> str:
        """Gera hash SHA-256 do conteúdo binário de um arquivo (integridade do PDF original)."""
        with open(caminho_arquivo, "rb") as arquivo:
            return hashlib.sha256(arquivo.read()).hexdigest()

    @staticmethod
    def _criar_pagina_auditoria(
        token: str,
        dados_cliente: Dict[str, str],
        imagem_assinatura_path: str,
        auditoria_dados: Dict[str, str],
        caminho_saida: str,
    ) -> None:
        """Passo A: cria PDF temporário com 1 página (assinatura + log jurídico) via fpdf."""
        pdf = FPDF()
        pdf.add_page()

        pdf.set_font("Arial", "B", 14)
        pdf.cell(
            200,
            10,
            txt="CERTIFICADO DE ASSINATURA ELETRÔNICA - ELITE RODAS",
            ln=True,
            align="C",
        )
        pdf.ln(8)

        pdf.set_font("Arial", size=10)
        log_texto = (
            f"ID do Documento (Token): {token}\n"
            f"Assinado por: {dados_cliente['nome']}\n"
            f"Data e Hora da Assinatura: {auditoria_dados['data']}\n"
            f"Endereço IP Registrado: {auditoria_dados['ip']}\n"
            f"Dispositivo (User-Agent): {auditoria_dados['user_agent']}\n"
            f"Hash de Integridade do Arquivo Original: {auditoria_dados['hash']}\n"
        )
        pdf.multi_cell(0, 7, txt=log_texto)
        pdf.ln(10)

        pdf.set_font("Arial", "B", 11)
        pdf.cell(200, 8, txt="Assinatura do Cliente:", ln=True)
        pdf.image(imagem_assinatura_path, x=10, w=100)
        pdf.ln(5)

        pdf.set_font("Arial", size=9)
        pdf.multi_cell(
            0,
            6,
            txt="Assinatura capturada via plataforma interna Elite Rodas.",
        )

        pdf.output(caminho_saida)

    @staticmethod
    def gerar_pdf_assinado(
        token: str,
        dados_cliente: Dict[str, str],
        caminho_pdf_original: str,
        imagem_assinatura_path: str,
        auditoria_dados: Dict[str, str],
    ) -> str:
        """
        Mescla o PDF original com a página de assinatura e auditoria.

        Returns:
            Caminho completo do PDF final assinado (arquivo temporário local).
        """
        if not os.path.exists(caminho_pdf_original):
            raise FileNotFoundError(
                f"PDF original não encontrado: {caminho_pdf_original}"
            )
        if not os.path.exists(imagem_assinatura_path):
            raise FileNotFoundError(
                f"Imagem de assinatura não encontrada: {imagem_assinatura_path}"
            )

        os.makedirs(TEMP_DIR, exist_ok=True)

        caminho_auditoria_temp = os.path.join(TEMP_DIR, f"auditoria_temp_{token}.pdf")
        caminho_pdf_final = os.path.join(TEMP_DIR, f"{token}_assinado.pdf")

        try:
            GeradorContrato._criar_pagina_auditoria(
                token,
                dados_cliente,
                imagem_assinatura_path,
                auditoria_dados,
                caminho_auditoria_temp,
            )

            writer = PdfWriter()

            with open(caminho_pdf_original, "rb") as arquivo_original:
                leitor_original = PdfReader(arquivo_original)
                for pagina in leitor_original.pages:
                    writer.add_page(pagina)

            with open(caminho_auditoria_temp, "rb") as arquivo_auditoria:
                leitor_auditoria = PdfReader(arquivo_auditoria)
                for pagina in leitor_auditoria.pages:
                    writer.add_page(pagina)

            with open(caminho_pdf_final, "wb") as arquivo_final:
                writer.write(arquivo_final)

        except Exception as exc:
            raise RuntimeError(f"Falha ao mesclar PDFs: {exc}") from exc
        finally:
            if os.path.exists(caminho_auditoria_temp):
                os.remove(caminho_auditoria_temp)

        return caminho_pdf_final
