"""Gera um PDF de exemplo (regulamento fictício de estágio) em data/docs/.

Uso:  python scripts/generate_sample_pdf.py
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUTPUT = Path("data/docs/regulamento_estagio_exemplo.pdf")

# Cada item é uma página: (título, [parágrafos])
PAGES = [
    (
        "Regulamento de Estágio Supervisionado - Faculdade Exemplo",
        [
            "Capítulo I - Das disposições gerais. O estágio supervisionado é uma atividade "
            "acadêmica que integra o currículo dos cursos de graduação da Faculdade Exemplo. "
            "Seu objetivo é complementar a formação do aluno por meio da vivência prática em "
            "ambientes profissionais relacionados ao seu curso.",
            "Art. 1º O estágio pode ser obrigatório, quando exigido pela matriz curricular, ou "
            "não obrigatório, quando realizado por escolha do aluno como atividade opcional.",
            "Art. 2º Para iniciar o estágio, o aluno deve estar regularmente matriculado e ter "
            "cursado, no mínimo, 40% da carga horária total do curso. Alunos com matrícula "
            "trancada não podem iniciar nem manter contratos de estágio.",
        ],
    ),
    (
        "Capítulo II - Da carga horária e da duração",
        [
            "Art. 3º A jornada de estágio não pode ultrapassar 6 (seis) horas diárias e 30 "
            "(trinta) horas semanais. Em períodos de provas, a jornada deve ser reduzida pela "
            "metade, mediante solicitação do aluno.",
            "Art. 4º A duração máxima de um contrato de estágio na mesma empresa é de 2 (dois) "
            "anos, exceto para estagiários com deficiência.",
            "Art. 5º O estágio obrigatório do curso de Sistemas de Informação exige o total de "
            "300 (trezentas) horas, que podem ser cumpridas a partir do 5º semestre.",
            "Art. 6º O estagiário tem direito a recesso de 30 dias a cada 12 meses de contrato, "
            "preferencialmente durante as férias escolares.",
        ],
    ),
    (
        "Capítulo III - Da documentação e do acompanhamento",
        [
            "Art. 7º Antes do início das atividades, devem ser assinados o Termo de Compromisso "
            "de Estágio (TCE) e o Plano de Atividades, com a concordância da empresa, do aluno e "
            "da Faculdade. Nenhuma atividade pode começar antes da assinatura do TCE.",
            "Art. 8º O aluno deve entregar um relatório de atividades a cada 6 (seis) meses de "
            "estágio e um relatório final ao término do contrato, ambos assinados pelo "
            "supervisor da empresa e pelo professor orientador.",
            "Art. 9º Cada estagiário será acompanhado por um professor orientador da Faculdade e "
            "por um supervisor na empresa. O supervisor deve ter formação ou experiência "
            "profissional na área do estágio e pode acompanhar até 10 estagiários simultaneamente.",
            "Art. 10 O descumprimento das regras deste regulamento pode levar ao cancelamento do "
            "estágio e à não validação das horas cumpridas.",
        ],
    ),
]


def main() -> None:
    styles = getSampleStyleSheet()
    story = []
    for index, (title, paragraphs) in enumerate(PAGES):
        story.append(Paragraph(title, styles["Heading2"]))
        story.append(Spacer(1, 12))
        for paragraph in paragraphs:
            story.append(Paragraph(paragraph, styles["BodyText"]))
            story.append(Spacer(1, 10))
        if index < len(PAGES) - 1:
            story.append(PageBreak())

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(OUTPUT), pagesize=A4, title="Regulamento de Estágio (exemplo)").build(story)
    print(f"PDF gerado em {OUTPUT}")


if __name__ == "__main__":
    main()
