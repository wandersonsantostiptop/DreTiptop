from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class Store(db.Model):
    __tablename__ = 'stores'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('User', backref='store', lazy=True)
    dre_entries = db.relationship('DREEntry', backref='store', lazy=True)

    def __repr__(self):
        return f'<Store {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    # roles: 'admin', 'manager', 'user'
    role = db.Column(db.String(20), default='user')
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

    def is_manager(self):
        return self.role in ('admin', 'manager')

    def __repr__(self):
        return f'<User {self.username}>'


class DREEntry(db.Model):
    __tablename__ = 'dre_entries'
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    regime_tributario = db.Column(db.String(20), default='simples')  # 'simples' or 'lucro_real'

    # ── INFORMAÇÕES GERENCIAIS ──────────────────────────────────────────────
    meta_vendas = db.Column(db.Float, default=0)
    pecas_vendidas = db.Column(db.Integer, default=0)
    atendimentos = db.Column(db.Integer, default=0)
    markup = db.Column(db.Float, default=0)
    estoque_qtd = db.Column(db.Integer, default=0)
    estoque_valor = db.Column(db.Float, default=0)

    # ── 1. FATURAMENTO BRUTO ────────────────────────────────────────────────
    fat_produtos = db.Column(db.Float, default=0)
    fat_outros = db.Column(db.Float, default=0)

    # ── 3. DESPESAS VARIÁVEIS - GERAIS ──────────────────────────────────────
    inadimplencia = db.Column(db.Float, default=0)
    marketing_local = db.Column(db.Float, default=0)
    # cartao_credito e cartao_debito são calculados (% sobre fat) mas podem ser sobrescritos
    cartao_credito_manual = db.Column(db.Float, default=None, nullable=True)
    cartao_debito_manual = db.Column(db.Float, default=None, nullable=True)
    embalagens_frete = db.Column(db.Float, default=0)
    fretes_extras = db.Column(db.Float, default=0)
    despesas_bancarias = db.Column(db.Float, default=0)
    dv_gerais_outros1 = db.Column(db.Float, default=0)
    dv_gerais_outros2 = db.Column(db.Float, default=0)

    # ── 4. DESPESAS VARIÁVEIS - PESSOAL ─────────────────────────────────────
    salario_gerente = db.Column(db.Float, default=0)
    salario_vendedores = db.Column(db.Float, default=0)
    salario_supervisora = db.Column(db.Float, default=0)
    salario_escritorio = db.Column(db.Float, default=0)
    gincanas_premios = db.Column(db.Float, default=0)
    fgts = db.Column(db.Float, default=0)
    inss = db.Column(db.Float, default=0)
    contrib_sindical = db.Column(db.Float, default=0)
    encargos_outros = db.Column(db.Float, default=0)
    vale_transporte = db.Column(db.Float, default=0)
    vale_refeicao = db.Column(db.Float, default=0)
    beneficios_outros = db.Column(db.Float, default=0)
    decimo_terceiro = db.Column(db.Float, default=0)
    ferias = db.Column(db.Float, default=0)
    rescisoes = db.Column(db.Float, default=0)
    pessoal_outros1 = db.Column(db.Float, default=0)
    pessoal_outros2 = db.Column(db.Float, default=0)

    # ── 5. CMV + ROYALTIES ──────────────────────────────────────────────────
    cmv_tdb = db.Column(db.Float, default=0)
    cmv_terceiros = db.Column(db.Float, default=0)
    royalties = db.Column(db.Float, default=0)
    diferencial_icms = db.Column(db.Float, default=0)

    # ── 6. CUSTOS FIXOS ─────────────────────────────────────────────────────
    pro_labore = db.Column(db.Float, default=0)
    contabilidade = db.Column(db.Float, default=0)
    limpeza = db.Column(db.Float, default=0)
    software_microvix = db.Column(db.Float, default=0)
    ecad = db.Column(db.Float, default=0)
    sonorizacao = db.Column(db.Float, default=0)
    pos_tef = db.Column(db.Float, default=0)
    seguros = db.Column(db.Float, default=0)
    manutencao_geral = db.Column(db.Float, default=0)
    giver_omnichannel = db.Column(db.Float, default=0)
    intranet = db.Column(db.Float, default=0)
    qlik_sense = db.Column(db.Float, default=0)
    internet = db.Column(db.Float, default=0)
    telefonia = db.Column(db.Float, default=0)
    aluguel_percentual = db.Column(db.Float, default=0)
    aluguel_minimo = db.Column(db.Float, default=0)
    condominio = db.Column(db.Float, default=0)
    fp_shopping = db.Column(db.Float, default=0)
    energia_eletrica = db.Column(db.Float, default=0)
    ar_condicionado = db.Column(db.Float, default=0)
    agua = db.Column(db.Float, default=0)
    iptu = db.Column(db.Float, default=0)
    outros_impostos_municipais = db.Column(db.Float, default=0)
    papelaria = db.Column(db.Float, default=0)
    provisao_inventario = db.Column(db.Float, default=0)
    uniformes = db.Column(db.Float, default=0)
    outros_gastos = db.Column(db.Float, default=0)
    viagens_treinamentos = db.Column(db.Float, default=0)
    cf_outros1 = db.Column(db.Float, default=0)
    cf_outros2 = db.Column(db.Float, default=0)

    # ── 8. RETIRADA ADICIONAL SÓCIOS ────────────────────────────────────────
    retirada_socios = db.Column(db.Float, default=0)

    # ── DESCONTO (%) ────────────────────────────────────────────────────────
    desconto_percent = db.Column(db.Float, default=0)

    # ── LUCRO REAL: receita acumulada 12 meses para cálculo de alíquota ──────
    receita_12_meses = db.Column(db.Float, default=None, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    __table_args__ = (
        db.UniqueConstraint('store_id', 'year', 'month', name='uq_store_year_month'),
    )

    def faturamento_bruto(self):
        return self.fat_produtos + self.fat_outros


class Parameter(db.Model):
    """Admin-configurable system parameters."""
    __tablename__ = 'parameters'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(300))
    category = db.Column(db.String(50), default='geral')

    def float_value(self):
        try:
            return float(self.value)
        except (ValueError, TypeError):
            return 0.0


class SimplesNacionalTable(db.Model):
    """Tabela progressiva do Simples Nacional (Anexo I - Comércio)."""
    __tablename__ = 'simples_table'
    id = db.Column(db.Integer, primary_key=True)
    min_revenue = db.Column(db.Float, nullable=False)
    max_revenue = db.Column(db.Float, nullable=False)
    rate = db.Column(db.Float, nullable=False)  # e.g. 0.04 = 4%

    def __repr__(self):
        return f'<SimplesTable {self.min_revenue}-{self.max_revenue}: {self.rate*100:.2f}%>'
