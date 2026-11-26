# Imovance 7.2 — gestão imobiliária

Projeto de portfólio com interface responsiva em português, backend Python e banco SQLite. [Acesse a demonstração](https://imovel-em-dia-portfolio.vercel.app). Ela utiliza dados fictícios armazenados no navegador, sem exigir cadastro, pagamento real ou API externa.

## Instalação local

Requisitos: Python 3.11 ou superior, sem bibliotecas externas de runtime. Clone o repositório e execute:

```bash
git clone https://github.com/JustJao1/imovance.git
cd imovance
python app.py
```

Acesse `http://localhost:8000` para utilizar o backend local e `http://localhost:8000/demo` para experimentar o modo demonstrativo. No Windows, o arquivo `Iniciar-Windows.bat` é um atalho opcional. O servidor utiliza loopback por padrão.

## Testes e compilação da demonstração

```bash
python -m unittest discover -s tests -v
node --check static/app.js
python scripts/build_demo.py
```

Os 15 testes cobrem autenticação, isolamento de organizações, inventário, compras, financeiro, reservas, recebíveis, estoque e integrações simuladas. O último comando gera `dist/index.html` para hospedagem estática.

## Recursos e limites

Gerenciamento de imóveis e inventário, reposição automática de pendências, reservas sem sobreposição, contas a receber com baixa transacional, limpeza, vistorias, contratos, manutenção, fornecedores, estoque e relatórios. O backend usa senhas scrypt, tokens de sessão com hash, cookies HttpOnly e SameSite Strict, verificação de origem, idempotência e escopo por organização.

Pagamentos via Asaas e IA são opcionais e dependem de configuração e homologação separadas. Consulte `.env.example`; variáveis de ambiente não são carregadas automaticamente de um arquivo `.env`. Não publique credenciais, bancos locais, dados pessoais ou arquivos de sessão.

Esta versão é um projeto de portfólio, não um serviço comercial homologado. A demonstração não utiliza o backend Python. Não há recuperação de senha, portal externo, convites, permissões granulares, anexos, automação de cobrança recorrente ou integração WhatsApp em produção. O servidor de desenvolvimento não deve ser exposto publicamente. Produção exige HTTPS, proteção contra abuso, backups, revisão de segurança e privacidade.

Consulte também a [arquitetura](architecture.md), a [API](api.md) e o [README em inglês](../README.md).
