from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
from urllib.parse import quote
from PIL import Image
import os

# ================= CONFIG =================
app = Flask(__name__)
app.secret_key = "uma_senha_muito_forte_aqui"

# Uploads
UPLOAD_FOLDER = "static/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
MAX_SIZE = (800, 800)

# Database via ENV (Internal URL do Render)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "SQLALCHEMY_DATABASE_URI",
    "sqlite:///local.db"  # fallback local
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "SQLALCHEMY_DATABASE_URI",
    "sqlite:///local.db"  # <-- fallback local
)

db = SQLAlchemy(app)
with app.app_context():
        db.create_all()

# ================= MODELS =================
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    imagem = db.Column(db.String(200), nullable=True)

class Loja(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aberta = db.Column(db.Boolean, default=True)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    telefone = db.Column(db.String(50))
    total = db.Column(db.Float)
    data = db.Column(db.String(50))
    itens = db.relationship("Item", backref="pedido", cascade="all, delete-orphan")

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'))
    produto = db.Column(db.String(100))
    quantidade = db.Column(db.Integer)
    preco = db.Column(db.Float)

# ================= FUNÇÕES =================
def criar_registros_iniciais():
    with app.app_context():
        db.create_all()

        # Loja inicial
        if not Loja.query.get(1):
            loja = Loja(id=1, aberta=True)
            db.session.add(loja)

        # Produtos iniciais
        if Produto.query.count() == 0:
            produtos = [
                Produto(nome="Coxinha", preco=5.00, imagem="Coxinha.png"),
                Produto(nome="Refrigerante", preco=7.00, imagem="sem-imagem.png"),
                Produto(nome="Cento de salgado", preco=50.00, imagem="sem-imagem.png")
            ]
            db.session.add_all(produtos)

        db.session.commit()

def salvar_imagem_redimensionada(imagem, caminho):
    img = Image.open(imagem)
    img = img.convert("RGB")
    img.thumbnail(MAX_SIZE)
    img.save(caminho, optimize=True, quality=85)

def carregar_estado_loja():
    loja = Loja.query.get(1)
    return loja.aberta if loja else True

# ================= ROTAS =================
@app.route('/')
def index():
    produtos = Produto.query.all()
    loja_aberta = carregar_estado_loja()
    return render_template('index.html', produtos=produtos, loja_aberta=loja_aberta)

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

    pedido = Pedido(nome=nome, telefone=telefone, total=total, data=data_pedido)
    for item in itens:
        pedido.itens.append(Item(
            produto=item["produto"],
            quantidade=item["quantidade"],
            preco=item["preco"]
        ))

    db.session.add(pedido)
    db.session.commit()

    mensagem = f"🧾 Pedido #{pedido.id}\nNome: {nome}\nTelefone: {telefone}\n\nItens:\n"
    for item in itens:
        subtotal = item["quantidade"] * item["preco"]
        mensagem += f"- {item['produto']} ({item['quantidade']}x) R$ {subtotal:.2f}\n"
    mensagem += f"\nTotal: R$ {total:.2f}"
    mensagem_codificada = quote(mensagem)

    whatsapp_dona = "5527998825127"
    url_whatsapp = f"https://api.whatsapp.com/send?phone={whatsapp_dona}&text={mensagem_codificada}"

    return jsonify({"status": "ok", "url": url_whatsapp})

# ================= ADMIN =================
SENHA_DONA = "123456"

@app.route('/admin')
def admin():
    if not session.get("logado"):
        return redirect("/admin/login")
    produtos = Produto.query.all()
    loja_aberta = carregar_estado_loja()
    return render_template("admin.html", produtos=produtos, loja_aberta=loja_aberta)

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        senha = request.form.get("senha")
        if senha == SENHA_DONA:
            session["logado"] = True
            return redirect("/admin")
        else:
            return "senha incorreta"
    return render_template("login.html")

@app.route('/admin/logout')
def logout():
    session.pop("logado", None)
    return redirect("/admin/login")

@app.route('/admin/toggle_loja')
def toggle_loja():
    loja = Loja.query.get(1)
    if loja:
        loja.aberta = not loja.aberta
        db.session.commit()
    return redirect("/admin")

@app.route('/admin/add_produto', methods=['POST'])
def add_produto():
    if not session.get("logado"):
        return redirect("/admin/login")
    nome = request.form.get('nome')
    preco = request.form.get('preco')
    imagem = request.files.get('imagem')
    nome_arquivo = None
    if imagem and imagem.filename != "":
        nome_arquivo = secure_filename(imagem.filename)
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
        salvar_imagem_redimensionada(imagem, caminho)
    produto = Produto(nome=nome, preco=preco, imagem=nome_arquivo)
    db.session.add(produto)
    db.session.commit()
    return redirect("/admin")

@app.route('/admin/remover_produto/<int:id>')
def remover_produto(id):
    if not session.get("logado"):
        return redirect("/admin/login")
    produto = Produto.query.get(id)
    if produto:
        db.session.delete(produto)
        db.session.commit()
    return redirect("/admin")

# ================= MAIN =================
if __name__ == "__main__":
    criar_registros_iniciais()
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(host="0.0.0.0", port=5000, debug=True)
