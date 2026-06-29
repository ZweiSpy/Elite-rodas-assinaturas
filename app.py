"""
Camada de Interface — Elite Rodas Assinaturas MVP (Cloud).
Gerenciador de Assinaturas e Auditoria via Streamlit Community Cloud + Supabase.
"""

import os
from datetime import datetime
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo

import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

from database import TEMP_DIR, DatabaseHandler
from gerador_pdf import GeradorContrato

st.set_page_config(
    page_title="Elite Rodas - Assinaturas",
    layout="centered",
    initial_sidebar_state="collapsed",
)

os.makedirs(TEMP_DIR, exist_ok=True)
db = DatabaseHandler()

MODELOS_SCOOTER = [ "X13 Pro Max",
    "X13 Pro",
    "X16 Pro",
    "X17",
    "X18",
    "Tank",
    "Sport 701",
    "Triciclo Big",
    "X11",
    "X13",
    "X15",
    "M16",
    "DOT"]


def obter_base_url() -> str:
    """Lê BASE_URL dos secrets do Streamlit Cloud (fallback vazio)."""
    return st.secrets.get("BASE_URL", "").rstrip("/")


def limpar_arquivo(caminho: Optional[str]) -> None:
    """Remove arquivo temporário local se existir."""
    if caminho and os.path.exists(caminho):
        os.remove(caminho)


def obter_dimensoes_canvas() -> Tuple[int, int]:
    """Retorna largura e altura do canvas otimizadas para assinatura mobile."""
    return 360, 200


def canvas_tem_traco(canvas_result) -> bool:
    """Verifica se o cliente desenhou algo no canvas."""
    if canvas_result is None or canvas_result.json_data is None:
        return False
    return len(canvas_result.json_data.get("objects", [])) > 0


def carregar_pdf_original(token: str, nome_arquivo_storage: str) -> bytes:
    """
    Baixa o PDF original do Supabase Storage para cache em memória (session_state).
    Arquivo em disco é efêmero e removido após leitura.
    """
    cache_key = f"pdf_original_{token}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    caminho_temp = os.path.join(TEMP_DIR, f"{token}_original_leitura.pdf")
    try:
        db.download_pdf(nome_arquivo_storage, caminho_temp)
        with open(caminho_temp, "rb") as arquivo:
            conteudo = arquivo.read()
        st.session_state[cache_key] = conteudo
        return conteudo
    finally:
        limpar_arquivo(caminho_temp)


def painel_vendedor() -> None:
    """Tela interna: upload do PDF pronto + geração do link de assinatura."""
    st.title("Elite Rodas | Gerenciador de Assinaturas")
    st.write(
        "Faça upload do contrato em PDF, preencha os dados do cliente "
        "e gere o link de assinatura."
    )

    with st.form("form_novo_contrato"):
        arquivo_pdf = st.file_uploader(
            "Faça upload do contrato em PDF",
            type=["pdf"],
        )
        nome_cliente = st.text_input("Nome do Cliente")
        telefone_cliente = st.text_input("Telefone (WhatsApp) Ex: 11999999999")
        modelo_scooter = st.selectbox("Modelo da Scooter", MODELOS_SCOOTER)
        submit = st.form_submit_button("Gerar Link de Assinatura")

        if submit:
            if arquivo_pdf is None:
                st.error("Envie o contrato em PDF antes de gerar o link.")
                return
            if not nome_cliente.strip() or not telefone_cliente.strip():
                st.error("Preencha nome e telefone do cliente.")
                return

            caminho_temp: Optional[str] = None
            try:
                token_gerado = db.criar_contrato(
                    nome_cliente.strip(),
                    telefone_cliente.strip(),
                    modelo_scooter,
                )
                nome_arquivo_storage = f"{token_gerado}_original.pdf"
                caminho_temp = os.path.join(TEMP_DIR, nome_arquivo_storage)

                with open(caminho_temp, "wb") as destino:
                    destino.write(arquivo_pdf.getbuffer())

                db.upload_pdf(caminho_temp, nome_arquivo_storage)
            except Exception as exc:
                st.error(f"Erro ao criar contrato: {exc}")
                return
            finally:
                limpar_arquivo(caminho_temp)

            base_url = obter_base_url()
            if base_url:
                link_assinatura = f"{base_url}/?token={token_gerado}"
            else:
                link_assinatura = f"?token={token_gerado}"

            st.success("Link de assinatura gerado com sucesso!")
            st.code(link_assinatura, language="text")
            st.info(
                "Copie o link acima ou inicie o robô do WhatsApp para envio automático."
            )


def tela_assinatura_cliente(token: str) -> None:
    """Tela externa: leitura do PDF original + desenho da assinatura."""
    if not token or not token.strip():
        st.error("Link inválido: token não informado.")
        return

    token = token.strip()

    try:
        dados_contrato = db.buscar_contrato(token)
    except Exception as exc:
        st.error(f"Erro ao consultar contrato: {exc}")
        return

    if not dados_contrato:
        st.error("Documento não encontrado ou link inválido.")
        return

    if dados_contrato["status"] == "Assinado":
        st.warning("Este documento já foi assinado.")
        st.info("Se precisar de uma nova via, entre em contato com a Elite Rodas.")
        return

    st.title("Assinatura de Contrato - Elite Rodas")
    st.write(f"**Olá, {dados_contrato['nome']}!**")
    st.write(
        f"Você está prestes a assinar o contrato referente à scooter modelo "
        f"**{dados_contrato['modelo']}**."
    )
    st.write("Leia o contrato abaixo antes de assinar.")

    st.markdown("---")

    nome_arquivo_storage = dados_contrato.get("caminho_pdf_original", "")
    if not nome_arquivo_storage:
        st.error("Arquivo do contrato não encontrado. Entre em contato com a Elite Rodas.")
        return

    try:
        pdf_bytes = carregar_pdf_original(token, nome_arquivo_storage)
        st.download_button(
            label="Baixar/Ler Contrato",
            data=pdf_bytes,
            file_name="Contrato_Elite_Rodas.pdf",
            mime="application/pdf",
            key=f"download_contrato_{token}",
        )
    except Exception as exc:
        st.error(f"Não foi possível carregar o contrato: {exc}")
        return

    st.markdown("---")

    st.write("### Área de Assinatura")
    st.caption("Use o mouse ou o dedo (no celular) para assinar.")

    largura, altura = obter_dimensoes_canvas()

    canvas_result = st_canvas(
        fill_color="rgba(255, 255, 255, 0)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#ffffff",
        height=altura,
        width=largura,
        drawing_mode="freedraw",
        display_toolbar=False,
        key=f"canvas_{token}",
    )

    if st.button("Finalizar Assinatura", key=f"btn_finalizar_{token}"):
        if not canvas_tem_traco(canvas_result):
            st.error("Por favor, faça sua assinatura antes de finalizar.")
            return

        caminho_original: Optional[str] = None
        caminho_assinatura: Optional[str] = None
        pdf_gerado: Optional[str] = None
        pdf_bytes_download: Optional[bytes] = None

        try:
            if canvas_result.image_data is None:
                st.error("Não foi possível capturar a assinatura. Tente novamente.")
                return

            caminho_original = os.path.join(TEMP_DIR, f"{token}_original_assinatura.pdf")
            caminho_assinatura = os.path.join(TEMP_DIR, f"assinatura_{token}.png")

            db.download_pdf(nome_arquivo_storage, caminho_original)

            img_array = canvas_result.image_data
            imagem = Image.fromarray(img_array.astype("uint8"), "RGBA")
            imagem.save(caminho_assinatura)

            try:
                headers = st.context.headers
                ip_cliente = (
                    headers.get("X-Forwarded-For", "IP Indisponível").split(",")[0].strip()
                )
                user_agent_cliente = headers.get("User-Agent", "Dispositivo Indisponível")
            except AttributeError:
                ip_cliente = "Erro de Captura"
                user_agent_cliente = "Erro de Captura"

            data_hora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            hash_documento = GeradorContrato.gerar_hash_arquivo(caminho_original)

            auditoria: Dict[str, str] = {
                "data": data_hora,
                "ip": ip_cliente,
                "user_agent": user_agent_cliente,
                "hash": hash_documento,
            }

            pdf_gerado = GeradorContrato.gerar_pdf_assinado(
                token,
                dados_contrato,
                caminho_original,
                caminho_assinatura,
                auditoria,
            )

            nome_arquivo_assinado = f"{token}_assinado.pdf"
            db.upload_pdf(pdf_gerado, nome_arquivo_assinado)

            with open(pdf_gerado, "rb") as arquivo_final:
                pdf_bytes_download = arquivo_final.read()

            db.registrar_assinatura(
                token, ip_cliente, user_agent_cliente, hash_documento
            )

        except ValueError as exc:
            st.warning(str(exc))
            return
        except FileNotFoundError as exc:
            st.error(f"Erro ao processar assinatura: {exc}")
            return
        except Exception as exc:
            st.error(f"Erro inesperado ao finalizar assinatura: {exc}")
            return
        finally:
            limpar_arquivo(caminho_original)
            limpar_arquivo(caminho_assinatura)
            limpar_arquivo(pdf_gerado)
            cache_key = f"pdf_original_{token}"
            if cache_key in st.session_state:
                del st.session_state[cache_key]

        st.success("Obrigado! Seu contrato foi assinado com sucesso.")
        st.balloons()

        if pdf_bytes_download:
            st.download_button(
                label="Baixar minha via do Contrato (PDF)",
                data=pdf_bytes_download,
                file_name="Meu_Contrato_Elite_Rodas_Assinado.pdf",
                mime="application/pdf",
                key=f"download_assinado_{token}",
            )


def main() -> None:
    """Roteador: token na URL → tela do cliente; caso contrário → painel vendedor."""
    params = st.query_params

    if "token" in params:
        token_param = params["token"]
        token = token_param[0] if isinstance(token_param, list) else token_param
        tela_assinatura_cliente(token)
    else:
        painel_vendedor()


if __name__ == "__main__":
    main()
