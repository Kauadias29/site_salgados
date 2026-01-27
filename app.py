import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, jsonify
import json
from urllib.parse import quote
from werkzeug.utils import secure_filename
import os
from PIL import Image
import os





app = Flask(__name__)


MAX_sizer = ( 800, 800) #largura x altura

UPLOAD_FOLDER = "static/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = "uma_senha_muito_forte_aqui"
SENHA_DONA = "123456"
whatsapp_dona = "5527998825127"

def get_db_connection():
    conn = sqlite3.connect('pedidos.db')
    conn.row_factory = sqlite3.Row
    return conn

def criar_tabela():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            imagem TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            telefone TEXT,
            total REAL,
            data TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER,
            produto TEXT,
            quantidade INTEGER,
            preco REAL,
            FOREIGN KEY(pedido_id) REFERENCES pedidos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loja (
            id INTEGER PRIMARY KEY,
            aberta INTEGER
        )
    """)

    # garante que exista registro da loja
    cursor.execute("SELECT COUNT(*) FROM loja")
    resultado = cursor.fetchone()
    if resultado[0] == 0:
        cursor.execute("INSERT INTO loja(id, aberta) VALUES (1, 1)")

    conn.commit()
    conn.close()

def inserir_produtos():
    conn = get_db_connection()
    cursor = conn.cursor()

    count = cursor.execute("SELECT COUNT(*) FROM produtos").fetchone()[0]

    if count == 0:
        produtos = [
            ("Coxinha", 5.00, "Coxinha.png"),
            ("Refrigerante", 7.00,"sem-imagem.png"),
            ("Cento de salgado", 50.00,"sem-imagem.png")
        ]
        cursor.executemany("INSERT INTO produtos (nome, preco, imagem) VALUES (?, ?,?)", produtos)

    conn.commit()
    conn.close()

def carregar_estado_loja():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT aberta FROM loja WHERE id = 1")
    resultado = cursor.fetchone()
    conn.close()

    if resultado:
        return bool(resultado["aberta"])

    return True

# CHAMADAS IMPORTANTES
criar_tabela()
inserir_produtos()
loja_aberta = carregar_estado_loja()

@app.route('/')
def index():
    conn = get_db_connection()
    produtos = conn.execute("SELECT * FROM produtos").fetchall()
    conn.close()

    return render_template('index.html', produtos=produtos, loja_aberta=loja_aberta)


def salvar_imagem_redimensionada(imagem, caminho):
    img = Image.open(imagem)
    img = img.convert("RGB")
    img.thumbnail(MAX_sizer)
    img.save(caminho, optimize=True, quality=85)


# ROTA FINAL (SALVAR PEDIDO + WHATSAPP)
@app.route('/salvar_pedido', methods=['POST'])
def salvar_pedido():
    data = request.get_json()

    nome = data.get('nome')
    telefone = data.get('telefone')
    itens = data.get('itens')

    if not nome or not telefone or not itens:
        return jsonify({"status": "erro", "mensagem": "Dados incompletos"})

    total = sum([item["quantidade"] * item["preco"] for item in itens])
    data_pedido = datetime.now().strftime("%d/%m/%Y %H:%M")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO pedidos (nome, telefone, total, data)
            VALUES (?,?,?,?)
        """, (nome, telefone, total, data_pedido))

        pedido_id = cursor.lastrowid

        for item in itens:
            cursor.execute("""
                INSERT INTO itens (pedido_id, produto, quantidade, preco)
                VALUES (?, ?, ?, ?)
            """, (pedido_id, item["produto"], item["quantidade"], item["preco"]))

        conn.commit()

    except Exception as e:
        conn.rollback()
        return jsonify({"status": "erro", "mensagem": str(e)})

    finally:
        conn.close()

    # monta a mensagem do WhatsApp
    mensagem = f"🧾 Pedido #{pedido_id}\n"
    mensagem += f"Nome: {nome}\n"
    mensagem += f"Telefone: {telefone}\n\n"
    mensagem += "Itens:\n"

    for item in itens:
        subtotal = item["quantidade"] * item["preco"]
        mensagem += f"- {item['produto']} ({item['quantidade']}x) R$ {subtotal:.2f}\n"

    mensagem += f"\nTotal: R$ {total:.2f}"
    mensagem_codificada = quote(mensagem)

    numero_dona = "5527998825127"
    url_whatsapp = f"https://api.whatsapp.com/send?phone={whatsapp_dona}&text={mensagem_codificada}"

    return jsonify({"status": "ok", "url": url_whatsapp})



# rota para ver pedidos
@app.route('/pedidos')
def ver_pedidos():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM pedidos ORDER BY id DESC")
    pedidos = cursor.fetchall()

    html = """
    <h2>📋 Pedidos Recebidos</h2>
    <table border="1" cellpadding="8">
        <tr>
            <th>ID</th>
            <th>Nome</th>
            <th>Produtos</th>
            <th>Total</th>
            <th>Data</th>
        </tr>
    """

    for p in pedidos:
        cursor.execute("SELECT produto, quantidade, preco FROM itens WHERE pedido_id = ?", (p[0],))
        itens = cursor.fetchall()

        lista_itens = ""
        for it in itens:
            lista_itens += f"{it['produto']} ({it['quantidade']}x) - R$ {it['preco']}<br>"

        html += f"""
        <tr>
            <td>{p['id']}</td>
            <td>{p['nome']}</td>
            <td>{lista_itens}</td>
            <td>R$ {p['total']}</td>
            <td>{p['data']}</td>
        </tr>
        """

    html += "</table>"
    conn.close()
    return html

# ================= LOJA =================



@app.route('/admin/toggle_loja')
def toggle_loja():
    global loja_aberta
    loja_aberta = not loja_aberta
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE loja SET aberta = ? WHERE id = 1",(1 if loja_aberta else 0,))
    conn.commit()
    conn.close()
    
    return redirect("/admin")

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get("logado"):
        return redirect("/admin/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form.get('nome')
        preco = request.form.get('preco')
        imagem = request.files.get('imagem')

        # imagem padrão
        nome_arquivo = "sem-imagem.png"

        # se enviou imagem
        if imagem and imagem.filename != "":
            nome_arquivo = secure_filename(imagem.filename)
            caminho = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
            salvar_imagem_redimensionada(imagem, caminho)

        cursor.execute(
            "INSERT INTO produtos (nome, preco, imagem) VALUES (?, ?, ?)",
            (nome, preco, nome_arquivo)
        )
        conn.commit()
        conn.close()

        return redirect("/admin")

    produtos = cursor.execute("SELECT * FROM produtos").fetchall()
    conn.close()

    return render_template(
        "admin.html",
        loja_aberta=loja_aberta,
        produtos=produtos
    )

@app.route('/admin/remover_produto/<int:id>')
def remover_produto(id):
    if not session.get("logado"):
        return redirect("/admin/login")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM produtos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    return redirect("/admin")   
    
@app.route('/admin/login')
def login():
    return render_template("login.html")
    
@app.route('/admin/login', methods=["POST"])
def login_post():
    senha = request.form.get ("senha")
    
    if senha == SENHA_DONA:
        session["logado"] = True
        return redirect("/admin")
    
    else:
        return "senha incorreta"
    
@app.route('/admin/logout')
def logout():
    session.pop("logado", None)
    return redirect("/admin/login")


if __name__ == "__main__":
    criar_tabela
    app.run(host="0.0.0.0", port=500, debug=True)
   