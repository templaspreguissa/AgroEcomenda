# Publicar o AgroEncomenda na internet (PythonAnywhere)

Passo a passo para deixar o site no ar, de graça, em `https://SEU_USUARIO.pythonanywhere.com`. Leva uns 20 minutos. Nos comandos, troque `SEU_USUARIO` pelo nome de usuário escolhido no cadastro.

## Por que o PythonAnywhere

| Exigência do projeto | PythonAnywhere (plano gratuito) |
|---|---|
| O banco SQLite e as fotos ficam em arquivos (`instance/`) e não podem sumir | Os arquivos ficam guardados (512 MiB de disco) |
| Aplicação Flask (WSGI) | Suporte próprio para Flask, com Python 3.13 |
| A carga de municípios usa a API do IBGE | `servicodados.ibge.gov.br` está na [lista de sites liberados](https://www.pythonanywhere.com/whitelist/) da conta gratuita |
| Sem cartão de crédito | Não pede |

A alternativa mais comum, o plano gratuito do Render, **apaga os arquivos** a cada reinício e o serviço dorme depois de 15 minutos sem acesso ([documentação do Render](https://render.com/docs/free)). Com isso, o banco SQLite e as fotos se perderiam.

**Limites do plano gratuito** ([Free Accounts Features](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/); [mudanças de 2026](https://blog.pythonanywhere.com/221/)):

- um site, com um processo;
- 512 MiB de disco;
- 100 segundos de CPU por dia nos consoles;
- **o site para depois de 1 mês** se ninguém renovar. Para renovar, entre na aba **Web** e clique no botão que estende o prazo. Dá para renovar quantas vezes quiser.

## 0. Antes: o código precisa estar no GitHub

O servidor copia o projeto do GitHub. Antes de continuar, rode no seu computador os comandos de Git da última entrega, na ordem, até o `git push`.

## 1. Criar a conta (você)

1. Acesse <https://www.pythonanywhere.com>, clique em **Pricing & signup** e depois em **Create a Beginner account**.
2. O **nome de usuário** vira o endereço do site (`nome.pythonanywhere.com`). Escolha algo como `agroencomenda` ou o nome do grupo.
3. Confirme o e-mail que eles enviarem.

## 2. Baixar o projeto e instalar as dependências

No PythonAnywhere, abra **Consoles › Bash** e rode, um por vez:

```bash
git clone https://github.com/templaspreguissa/AgroEcomenda.git
```

```bash
cd ~/AgroEcomenda
```

```bash
python3.13 -m venv ~/.virtualenvs/agroencomenda
```

```bash
source ~/.virtualenvs/agroencomenda/bin/activate
```

```bash
pip install -r requirements.txt
```

## 3. Criar a chave secreta

A chave protege o login (assina o cookie da sessão). O comando abaixo sorteia uma e grava em `instance/config.py`, que fica só no servidor (a pasta `instance/` não vai para o Git):

```bash
mkdir -p instance && python -c "import secrets; print('SECRET_KEY = ' + repr(secrets.token_hex(32)))" > instance/config.py
```

Não copie essa chave para nenhum outro lugar.

## 4. Criar o banco e carregar os dados

Ainda no console, na pasta `~/AgroEcomenda` e com o ambiente ativado:

```bash
flask --app app init-db --yes
```

```bash
flask --app app carregar-municipios MG
```

Repita o último comando com outras UFs se quiser aceitar cadastros de outros estados (por exemplo, `GO` ou `SP`). Cada UF a mais deixa a lista de municípios das páginas maior.

Para a apresentação, carregue os dados fictícios:

```bash
flask --app app carregar-demo
```

O comando mostra **duas senhas sorteadas**: uma para `ana`, `carlos`, `jose`, `rita`, `paulo` e `marina`, e outra para `admin.demo@example.com`. **Anote as duas na hora**: elas não ficam guardadas e não aparecem de novo. A primeira pode ser passada para quem for avaliar o site. A da administração, só para o grupo.

> **Nunca rode `carregar-demo --senha-fixa` no servidor.** A senha fixa está em `app/demo.py`, que é público no GitHub, e qualquer pessoa entraria como administração.

## 5. Criar o site

Na aba **Web**:

1. **Add a new web app** › Next › **Manual configuration (including virtualenvs)** › **Python 3.13** › Next. Não escolha a opção "Flask": ela cria um projeto de exemplo.
2. Em **Code**:
   - **Source code:** `/home/SEU_USUARIO/AgroEcomenda`
   - **WSGI configuration file:** clique no link, **apague tudo** o que estiver no arquivo, cole o texto abaixo, troque `SEU_USUARIO` e clique em **Save**:

     ```python
     import sys

     projeto = "/home/SEU_USUARIO/AgroEcomenda"
     if projeto not in sys.path:
         sys.path.insert(0, projeto)

     from app import create_app

     application = create_app()
     ```

3. Em **Virtualenv:** `/home/SEU_USUARIO/.virtualenvs/agroencomenda`
4. Em **Static files**, adicione URL `/static/` e Directory `/home/SEU_USUARIO/AgroEcomenda/app/static`. Assim o CSS e o JavaScript são entregues direto pelo servidor, sem ocupar o processo do site.
5. Em **Security**, ligue **Force HTTPS**. Isso é **obrigatório**: fora do modo de desenvolvimento, o cookie de login só vale em HTTPS, então pelo endereço `http://` não daria para entrar.
6. No topo da página, clique em **Reload**.

## 6. Conferir

1. Abra `https://SEU_USUARIO.pythonanywhere.com`. A página inicial deve aparecer com as três portas.
2. Entre como `marina.demo@example.com`, com a primeira senha do passo 4, e abra **Produtos**.
3. Saia e entre como `admin.demo@example.com`, com a segunda senha. O link **Administração** aparece no topo.
4. Se der erro, abra a aba **Web**, role até **Log files** e veja o **Error log**. A causa costuma estar nas últimas linhas.

Os testes automáticos (334) devem ser rodados no seu computador, não no servidor. Eles levam alguns minutos e gastariam a cota diária de CPU do plano gratuito.

## Manutenção

| Tarefa | Como fazer |
|---|---|
| Manter o site no ar | Uma vez por mês, aba **Web** › botão que estende o prazo |
| Publicar uma versão nova | Depois do `git push` no seu computador: console Bash › `cd ~/AgroEcomenda && git pull` › aba **Web** › **Reload** |
| Versão nova que muda o banco | Além do `git pull`, refaça o passo 4. **O `init-db` apaga todos os dados**, inclusive cadastros de pessoas reais |
| Alguém esqueceu a senha | O site não envia e-mail. O link de nova senha aparece no **Error log** (linha "link para criar nova senha"). Só entregue o link para quem você tem certeza de ser o dono do e-mail da conta |
| Dar o papel de administração à sua conta | No console, com o ambiente ativado: `flask --app app tornar-admin seu@email` |
| Recomeçar a demonstração do zero | Refaça o passo 4 e clique em **Reload** |

Em todo console novo, rode antes `cd ~/AgroEcomenda` e `source ~/.virtualenvs/agroencomenda/bin/activate`.

## Cuidados

- O site é **público**: qualquer pessoa pode se cadastrar. O rodapé, a tela de cadastro, os Termos e a Política de Privacidade avisam que é um projeto acadêmico e pedem dados fictícios. Mesmo assim, se alguém usar dados reais, eles ficam sob responsabilidade do grupo (LGPD).
- Os dados de demonstração são fictícios. Os e-mails usam o domínio reservado `example.com` e os CNPJs começam com `DEMO`.
- A chave secreta e o banco ficam só em `instance/`, no servidor. Não suba essa pasta para o GitHub.
- O texto dos contratos é um modelo acadêmico e não substitui revisão jurídica.
