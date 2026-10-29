"""Gera os documentos de exemplo da demo em data/docs/, um de cada formato aceito.

- manual_cafeteira_aurora.pdf: manual de produto, com uma tabela de códigos de erro
- política_trabalho_remoto.docx: política interna de uma empresa
- contrato_prestação_serviços.txt: contrato simples de prestação de serviços

Os nomes têm acento porque viram o título do documento na interface.
Todo o conteúdo é fictício. Uso:  python scripts/generate_samples.py
"""

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUTPUT_DIR = Path("data/docs")

# ---------- PDF: manual de produto ----------

MANUAL_INTRO = [
    "Obrigado por escolher a Cafeteira Aurora C3. Leia este manual antes do primeiro uso e "
    "guarde-o para consultas futuras.",
    "Antes do primeiro uso: lave o reservatório e a jarra com água e detergente neutro. Em "
    "seguida, faça dois ciclos completos só com água, sem pó de café, e descarte a água.",
    "Capacidade: o reservatório comporta 1,2 litro de água, o que rende até 12 xícaras. Não "
    "ultrapasse a marcação MAX, porque a água pode transbordar pelo filtro.",
    "Desligamento automático: a placa de aquecimento mantém o café quente por 40 minutos. Depois "
    "disso, a cafeteira desliga sozinha para economizar energia.",
]

MANUAL_CARE = [
    "Limpeza diária: lave a jarra e o porta-filtro após cada uso. Não use esponjas abrasivas na "
    "placa de aquecimento.",
    "Descalcificação: a cada 40 ciclos, ou quando o aviso CAL acender, encha o reservatório com "
    "uma mistura de 1 parte de vinagre branco para 2 partes de água e faça um ciclo sem café. "
    "Depois, faça dois ciclos só com água para tirar o cheiro do vinagre.",
    "Garantia: a Cafeteira Aurora C3 tem garantia de 12 meses contra defeitos de fabricação, "
    "contados a partir da data da nota fiscal. A garantia não cobre danos por queda, uso de "
    "voltagem errada ou falta de descalcificação.",
]

ERROR_CODES = [
    ["Código", "Significado", "O que fazer"],
    ["E1", "Reservatório sem água", "Encha o reservatório até a marcação desejada."],
    ["E2", "Superaquecimento", "Desligue da tomada e espere 15 minutos."],
    ["E3", "Sensor de temperatura com falha", "Procure a assistência técnica autorizada."],
    ["CAL", "Excesso de calcário", "Faça a descalcificação descrita na página 2."],
]


def build_manual(path: Path) -> None:
    styles = getSampleStyleSheet()
    body, title = styles["BodyText"], styles["Heading2"]
    story = [Paragraph("Manual de uso - Cafeteira Aurora C3", title), Spacer(1, 12)]
    for text in MANUAL_INTRO:
        story += [Paragraph(text, body), Spacer(1, 10)]
    story += [PageBreak(), Paragraph("Cuidados, limpeza e garantia", title), Spacer(1, 12)]
    for text in MANUAL_CARE:
        story += [Paragraph(text, body), Spacer(1, 10)]
    story += [PageBreak(), Paragraph("Códigos de erro no visor", title), Spacer(1, 12)]
    table = Table(ERROR_CODES, colWidths=[50, 170, 230])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(table)
    SimpleDocTemplate(str(path), pagesize=A4, title="Manual da Cafeteira Aurora C3 (exemplo)").build(story)


# ---------- Word: política interna ----------

REMOTE_POLICY = [
    "Política de Trabalho Remoto - Exemplo Tecnologia Ltda.",
    "1. Objetivo. Esta política define as regras para o trabalho remoto dos colaboradores da "
    "Exemplo Tecnologia Ltda., em vigor a partir de 1º de março de 2026.",
    "2. Modelo híbrido. Os colaboradores podem trabalhar de casa até 3 (três) dias por semana. "
    "Terças e quintas-feiras são dias presenciais obrigatórios para todas as equipes.",
    "3. Horário. O horário de disponibilidade é das 10h às 16h. Fora dessa faixa, cada pessoa "
    "organiza a própria jornada, respeitando o total de 40 horas semanais.",
    "4. Equipamentos. A empresa fornece notebook, monitor e headset. Quem trabalha remotamente "
    "recebe um auxílio mensal de R$ 150,00 para internet e energia, pago junto com o salário.",
    "5. Segurança da informação. É obrigatório usar a VPN da empresa para acessar sistemas "
    "internos. Não é permitido trabalhar em redes Wi-Fi públicas sem a VPN ativa.",
    "6. Trabalho do exterior. Trabalhar de outro país exige aprovação prévia do RH, com pedido "
    "feito com pelo menos 30 dias de antecedência, e é limitado a 60 dias por ano.",
]


def build_docx(path: Path, paragraphs: list[str]) -> None:
    """Cria um .docx mínimo válido (abre no Word), sem depender de bibliotecas extras."""
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    body = "".join(f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>" for text in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", rels)
        docx.writestr("word/document.xml", document)


# ---------- TXT: contrato ----------

CONTRACT = """CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE DESENVOLVIMENTO DE SITE

CONTRATANTE: Padaria Exemplo Ltda.
CONTRATADA: Estúdio Exemplo de Design Ltda.

CLÁUSULA 1 - OBJETO
A CONTRATADA vai desenvolver o site institucional da CONTRATANTE, com até 5 páginas,
formulário de contato e versão para celular.

CLÁUSULA 2 - PRAZO
O site será entregue em até 45 dias corridos, contados da assinatura deste contrato e do
envio, pela CONTRATANTE, dos textos e das imagens.

CLÁUSULA 3 - VALOR E PAGAMENTO
O valor total é de R$ 6.000,00, pago em duas parcelas: 50% na assinatura e 50% na entrega.
Atrasos no pagamento geram multa de 2% e juros de 1% ao mês.

CLÁUSULA 4 - REVISÕES
Estão incluídas 2 rodadas de revisão após a entrega do layout. Revisões extras custam
R$ 150,00 por hora.

CLÁUSULA 5 - RESCISÃO
Qualquer uma das partes pode encerrar o contrato com aviso prévio de 15 dias. Se a
CONTRATANTE encerrar o contrato antes da entrega, sem culpa da CONTRATADA, pagará multa
de 20% sobre o valor que ainda falta pagar.

CLÁUSULA 6 - DIREITOS
Após o pagamento integral, todos os direitos sobre o site passam para a CONTRATANTE.
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    build_manual(OUTPUT_DIR / "manual_cafeteira_aurora.pdf")
    build_docx(OUTPUT_DIR / "política_trabalho_remoto.docx", REMOTE_POLICY)
    (OUTPUT_DIR / "contrato_prestação_serviços.txt").write_text(CONTRACT, encoding="utf-8")
    print(f"Exemplos gerados em {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
