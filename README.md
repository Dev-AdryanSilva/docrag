# DocRAG: assistente de documentos com RAG

Assistente que responde perguntas usando só os documentos enviados. Toda resposta cita o documento e a página; quando a informação não está nos documentos, ele responde "Não encontrei essa informação nos documentos".

- **Formatos:** PDF (inclusive com tabelas e em duas colunas), PDF escaneado (com OCR em português), Word (`.docx`) e texto (`.txt`).
- **Busca híbrida:** BM25 (palavras exatas) combinado com busca semântica (embeddings) por Reciprocal Rank Fusion.
- **LLM:** Gemini Flash-Lite, isolado em `app/llm.py` para ser trocado facilmente.

Para rodar tudo (banco, API e interface):

```bash
docker compose up --build
```

A interface abre em http://localhost:8501 e a API em http://localhost:8000/docs.

> O README completo (arquitetura, diagrama, exemplos com curl e como usei IA no projeto) entra na etapa 7.

## Acessibilidade

A interface segue a WCAG 2.2 nível AA até onde o Streamlit permite.

- **Tema claro e escuro:** segue o tema do sistema. Para trocar, use o menu ⋮ no canto superior direito e escolha *Light* (claro), *Dark* (escuro) ou *System* (sistema).
- **Contraste:** todos os pares de cor têm pelo menos 4.5:1 para texto e 3:1 para bordas e componentes, nos dois temas. As cores ficam em `.streamlit/config.toml` e viram tokens em `ui/styles.css`.
- **Opções na barra lateral (seção "Acessibilidade"):**
  - tamanho da fonte (Pequeno, Médio, Grande);
  - alto contraste;
  - reduzir animações. A preferência do sistema (`prefers-reduced-motion`) também é respeitada.
- **Teclado:** tudo funciona sem mouse, com um contorno de foco sempre visível.
- **Textos claros:**
  - botões com texto, nunca só ícone;
  - erros escritos por extenso ("Erro: ..."), não indicados só pela cor;
  - página marcada como `pt-BR`.
- **Celular:** funciona a partir de 375px de largura, sem rolagem horizontal e com botões de pelo menos 44px de altura.

### Prints

| Tema claro | Tema escuro |
|---|---|
| ![Tema claro](docs/tema-claro.png) | ![Tema escuro](docs/tema-escuro.png) |
