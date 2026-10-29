"""Interface do chatbot. Não acessa banco nem LLM: só consome a API via HTTP."""

import html
import os
import re
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

# Rodando local, lê o .env da raiz do projeto; no Docker as variáveis já vêm do compose
load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}
# Upload e perguntas podem demorar (embeddings e LLM)
TIMEOUT = 120

APP_NAME = "DocRAG"
STYLES_PATH = Path(__file__).parent / "styles.css"
FILE_TYPES = ["pdf", "docx", "txt"]
NOT_FOUND_MESSAGE = "Não encontrei essa informação nos documentos."
API_OFFLINE_MESSAGE = "Erro: não consegui falar com a API. Verifique se o servidor está rodando."
# Citação que o LLM escreve no texto, ex.: " (manual.pdf, p. 2)" ou " (politica.docx)".
# Na tela ela vai para "Fontes"
CITATION_PATTERN = re.compile(r"\s*\([^()]*\.(?:pdf|docx|txt)(?:, p\. \d+)?\)")
# Linha separadora de tabela Markdown, ex.: "|---|:---:|---|"
TABLE_SEPARATOR = re.compile(r"^\|?[\s:\-|]+\|?$")
USER_AVATAR = ":material/person:"
ASSISTANT_AVATAR = ":material/description:"

# Perguntas de exemplo, uma para cada documento gerado por scripts/generate_samples.py
# (PDF com tabela, Word e TXT), mostradas com a conversa vazia
SUGGESTIONS = [
    "O que significa o erro E3 na cafeteira?",
    "Quantos dias por semana posso trabalhar de casa?",
    "Qual a multa se o contrato for cancelado antes da entrega?",
]

# Opções de tamanho da fonte: texto mostrado na tela -> valor usado pelo CSS
FONT_SIZES = {"Pequeno": "small", "Médio": "medium", "Grande": "large"}

# Marca: uma folha de documento com linhas de texto. As cores vêm do styles.css
LOGO_SVG = (
    '<svg class="logo" width="44" height="44" viewBox="0 0 44 44" aria-hidden="true">'
    '<rect width="44" height="44" rx="10"/>'
    '<path class="logo-mark" d="M15 11h10l6 6v16H15z"/>'
    '<path class="logo-lines" d="M18.5 21h9M18.5 25h9M18.5 29h6"/></svg>'
)


def friendly_name(filename: str) -> str:
    """'manual_cafeteira.pdf' -> 'Manual cafeteira'."""
    name = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
    return name[:1].upper() + name[1:]


def plural(count: int, singular: str, plural_form: str) -> str:
    return f"{count} {singular if count == 1 else plural_form}"


def place(document: str, page: int | None) -> str:
    """Onde está um trecho: 'Manual, p. 2' ou só 'Politica' (Word e TXT não têm página)."""
    name = friendly_name(document)
    return name if page is None else f"{name}, p. {page}"


def plain_excerpt(text: str) -> str:
    """Tira a marcação Markdown do trecho para exibir como texto corrido.

    Os PDFs são guardados em Markdown (ajuda o LLM a ler tabelas), mas na tela
    "# **Título**" vira "Título" e a linha "|E1|Sem água|" vira "E1 · Sem água".
    Títulos e linhas de tabela ficam em linhas próprias; o texto corrido é emendado.
    """
    blocks: list[str] = []
    joining = False  # o último bloco é texto corrido que pode receber a próxima linha
    for line in text.splitlines():
        line = line.strip()
        if not line or TABLE_SEPARATOR.match(line):
            joining = False
            continue
        is_heading, is_row = line.startswith("#"), line.startswith("|")
        line = line.lstrip("#").replace("**", "").strip()
        if is_row:
            line = " · ".join(cell.strip() for cell in line.strip("|").split("|"))
        if joining and not (is_heading or is_row):
            blocks[-1] += " " + line
        else:
            blocks.append(line)
        joining = not (is_heading or is_row)
    return "\n".join(" ".join(block.split()) for block in blocks)


def document_details(document: dict) -> str:
    """'3 páginas · 4 trechos' para PDF; 'Word · 2 trechos' para formatos sem páginas."""
    chunks = plural(document["num_chunks"], "trecho", "trechos")
    if document["num_pages"]:
        return f"{plural(document['num_pages'], 'página', 'páginas')} · {chunks}"
    kind = "Word" if document["filename"].lower().endswith(".docx") else "Texto"
    return f"{kind} · {chunks}"


def error_message(response: requests.Response) -> str:
    """Monta o erro em texto claro, usando a mensagem que a API manda no campo "detail"."""
    try:
        return f"Erro: {response.json()['detail']}"
    except (ValueError, KeyError):
        return f"Erro: a API respondeu com o código {response.status_code}."


# ---------- Estilo e acessibilidade ----------


def load_css() -> None:
    """Carrega o ui/styles.css (o Streamlit coloca o conteúdo dentro de uma tag <style>)."""
    st.html(STYLES_PATH)


def apply_preferences() -> None:
    """Grava o idioma e as preferências de acessibilidade como atributos do <html>.

    O styles.css reage a esses atributos (ex.: html[data-font="large"]). É o único
    JavaScript da interface, porque o Streamlit não deixa mudar o <html> de outro jeito.
    """
    attributes = {
        "lang": "pt-BR",
        "data-font": FONT_SIZES[st.session_state.font_size],
        "data-contrast": "high" if st.session_state.high_contrast else "normal",
        "data-motion": "reduced" if st.session_state.reduce_motion else "normal",
    }
    script = "".join(
        f'document.documentElement.setAttribute("{name}", "{value}");'
        for name, value in attributes.items()
    )
    st.html(f"<script>{script}</script>", unsafe_allow_javascript=True)


# ---------- Chamadas à API ----------


def fetch_documents() -> list[dict] | None:
    """Lista os documentos; devolve None se a API estiver fora do ar."""
    try:
        return requests.get(f"{API_URL}/documentos", timeout=10).json()
    except requests.RequestException:
        return None


def send_question(question: str) -> None:
    st.session_state.messages.append({"role": "user", "content": question})
    payload = {"pergunta": question, "conversation_id": st.session_state.conversation_id}
    try:
        response = requests.post(f"{API_URL}/perguntar", json=payload, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException:
        st.session_state.error = API_OFFLINE_MESSAGE
        return

    if response.status_code != 200:
        st.session_state.error = error_message(response)
        return

    data = response.json()
    st.session_state.conversation_id = data["conversation_id"]
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": data["resposta"],
            "sources": data["fontes"],
            "message_id": data["mensagem_id"],
            "feedback": None,
        }
    )


def send_feedback(message: dict, useful: bool) -> None:
    """Chamada quando o usuário clica em "Útil" ou "Não útil"."""
    payload = {"mensagem_id": message["message_id"], "util": useful}
    try:
        response = requests.post(f"{API_URL}/feedback", json=payload, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException:
        st.session_state.error = "Erro: não consegui enviar o feedback. Verifique se o servidor está rodando."
        return
    if response.status_code == 200:
        message["feedback"] = useful
    else:
        st.session_state.error = error_message(response)


def upload_pdf(file) -> None:
    """Envia o PDF e guarda o resultado para mostrar depois do recarregamento da página."""
    files = {"file": (file.name, file.getvalue(), file.type)}
    try:
        response = requests.post(f"{API_URL}/documentos", files=files, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException:
        st.session_state.upload_notice = ("error", API_OFFLINE_MESSAGE)
        return
    if response.status_code == 201:
        document = response.json()
        text = f"Pronto: {friendly_name(document['filename'])} foi adicionado ({document_details(document)})."
        st.session_state.upload_notice = ("success", text)
    else:
        st.session_state.upload_notice = ("error", error_message(response))


# ---------- Ações dos botões ----------


def new_conversation() -> None:
    st.session_state.messages = []
    st.session_state.conversation_id = None


def ask_suggestion(question: str) -> None:
    # A pergunta é processada no corpo da página, onde o indicador de carregamento aparece
    st.session_state.pending_question = question


# ---------- Partes da tela ----------


def render_header(documents: list[dict] | None) -> None:
    if documents is None:
        notice = "Sem documentos disponíveis: a API não respondeu."
    elif not documents:
        notice = "Nenhum documento enviado ainda."
    else:
        chunks = sum(d["num_chunks"] for d in documents)
        notice = (
            f"Respostas baseadas só nos documentos enviados: "
            f"{plural(len(documents), 'documento', 'documentos')}, "
            f"{plural(chunks, 'trecho indexado', 'trechos indexados')}."
        )
    st.markdown(
        f'<div class="app-header">{LOGO_SVG}<div>'
        f"<h1>{APP_NAME}</h1>"
        '<p class="subtitle">Assistente de documentos com IA. Pergunte sobre seus PDFs, '
        "arquivos do Word e textos, e veja de qual documento e página veio cada resposta.</p>"
        f'<p class="notice">{notice}</p>'
        "</div></div>",
        unsafe_allow_html=True,
    )


def render_documents(documents: list[dict] | None) -> None:
    st.subheader("Documentos")
    if documents is None:
        st.error(
            "Erro: a API está fora do ar. Inicie o servidor e recarregue a página.",
            icon=":material/cloud_off:",
        )
    elif not documents:
        st.caption("Nenhum documento ainda. Envie um arquivo abaixo.")
    else:
        for document in documents:
            st.markdown(
                f"**{html.escape(friendly_name(document['filename']))}**  \n"
                f'<span class="muted">{document_details(document)}</span>',
                unsafe_allow_html=True,
            )

    notice = st.session_state.pop("upload_notice", None)
    if notice:
        kind, text = notice
        if kind == "success":
            st.success(text, icon=":material/check_circle:")
        else:
            st.error(text, icon=":material/error:")

    with st.expander("Adicionar documento", icon=":material/upload_file:"):
        uploaded = st.file_uploader(
            "Arquivo PDF, Word (.docx) ou TXT",
            type=FILE_TYPES,
            help=(
                "O arquivo é lido, dividido em trechos e indexado para a busca. Tabelas são "
                "preservadas e PDFs escaneados passam por OCR, o que pode levar mais tempo."
            ),
        )
        if st.button("Enviar documento", disabled=uploaded is None, width="stretch"):
            with st.spinner("Lendo o arquivo e preparando a busca..."):
                upload_pdf(uploaded)
            # Recarrega para a lista de documentos já mostrar o novo arquivo
            st.rerun()


def render_accessibility() -> None:
    st.subheader("Acessibilidade")
    # As chaves (key) guardam cada escolha no st.session_state durante a sessão
    st.radio(
        "Tamanho da fonte",
        list(FONT_SIZES),
        key="font_size",
        horizontal=True,
        help="Aumenta ou diminui todo o texto da página.",
    )
    st.toggle(
        "Alto contraste",
        key="high_contrast",
        help="Fundo puro, texto preto ou branco e bordas reforçadas.",
    )
    st.toggle(
        "Reduzir animações",
        key="reduce_motion",
        help="Desliga transições e animações. Se o sistema já pede menos movimento, isso é respeitado.",
    )
    st.caption(
        "**Tema claro ou escuro:** segue o do seu sistema. Para trocar, abra o menu ⋮ "
        "no canto superior direito e escolha *Light* (claro) ou *Dark* (escuro)."
    )


def render_sidebar(documents: list[dict] | None) -> None:
    with st.sidebar:
        st.button(
            "Nova conversa",
            icon=":material/add_comment:",
            type="primary",
            width="stretch",
            on_click=new_conversation,
            help="Limpa o chat e começa do zero. Os documentos continuam carregados.",
        )
        render_documents(documents)
        render_accessibility()
        apply_preferences()


def render_empty_state(documents: list[dict] | None) -> None:
    if not documents:
        st.write("Envie um arquivo em **Adicionar documento**, na barra lateral, para começar.")
        return
    st.write("Escreva sua pergunta no campo abaixo ou experimente uma destas:")
    with st.container(horizontal=True, gap="small"):
        for index, question in enumerate(SUGGESTIONS):
            st.button(
                question,
                key=f"suggestion_{index}",
                width="content",
                on_click=ask_suggestion,
                args=(question,),
            )


def render_sources(sources: list[dict]) -> None:
    # Resumo no título do expander: dá para ver as fontes mesmo com ele fechado
    # Ordena por documento e página (fontes sem página, como Word e TXT, contam como 0)
    places = sorted({(s["documento"], s["pagina"]) for s in sources}, key=lambda p: (p[0], p[1] or 0))
    summary = " · ".join(place(doc, page) for doc, page in places)
    with st.expander(f"Fontes: {summary}"):
        for source in sources:
            title = html.escape(place(source["documento"], source["pagina"]))
            excerpt = html.escape(plain_excerpt(source["trecho"]))
            st.markdown(
                f'<p class="source-title">{title}</p><div class="excerpt">{excerpt}…</div>',
                unsafe_allow_html=True,
            )


def render_feedback(message: dict) -> None:
    if message["feedback"] is not None:
        choice = "útil" if message["feedback"] else "não útil"
        st.caption(f"Feedback registrado: você marcou esta resposta como {choice}. Obrigado!")
        return
    # Container horizontal: pergunta e botões lado a lado
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.caption("Esta resposta ajudou?", width="content")
        # A chave usa o id da mensagem para não confundir respostas de conversas diferentes
        message_id = message["message_id"]
        st.button("Útil", key=f"useful_{message_id}", on_click=send_feedback, args=(message, True))
        st.button("Não útil", key=f"not_useful_{message_id}", on_click=send_feedback, args=(message, False))


def render_message(message: dict) -> None:
    avatar = USER_AVATAR if message["role"] == "user" else ASSISTANT_AVATAR
    with st.chat_message(message["role"], avatar=avatar):
        if message["role"] != "assistant":
            st.markdown(message["content"])
            return
        # Tira a citação do meio do texto: ela aparece organizada em "Fontes"
        st.markdown(CITATION_PATTERN.sub("", message["content"]) if message["sources"] else message["content"])
        if message["content"] == NOT_FOUND_MESSAGE:
            st.caption("Tente reformular a pergunta ou envie o documento que trata desse assunto.")
        elif message["sources"]:
            render_sources(message["sources"])
        render_feedback(message)


def main() -> None:
    st.set_page_config(page_title=f"{APP_NAME} · Assistente de documentos", page_icon=":material/description:")
    load_css()

    # session_state guarda dados entre um redesenho e outro da página
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("conversation_id", None)
    st.session_state.setdefault("error", None)
    st.session_state.setdefault("font_size", "Médio")
    st.session_state.setdefault("high_contrast", False)
    st.session_state.setdefault("reduce_motion", False)

    documents = fetch_documents()
    render_header(documents)
    render_sidebar(documents)

    if not st.session_state.messages:
        render_empty_state(documents)
    for message in st.session_state.messages:
        render_message(message)

    if st.session_state.error:
        st.error(st.session_state.error, icon=":material/error:")
        st.session_state.error = None

    # Texto curto para caber no campo mesmo em tela de celular
    typed = st.chat_input("Escreva sua pergunta...", disabled=not documents)
    question = typed or st.session_state.pop("pending_question", None)
    if question:
        # Mostra a pergunta na hora e o carregamento no lugar da resposta
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(question)
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            with st.spinner("Buscando nos documentos..."):
                send_question(question)
        st.rerun()


main()
