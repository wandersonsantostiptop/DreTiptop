import os
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from datetime import datetime

from models import db, User, Store, DREEntry, Parameter, SimplesNacionalTable
from calculations import calculate_dre, calculate_annual_summary


def _seed_defaults():
    """Insere parametros e dados iniciais se o banco estiver vazio."""
    defaults = [
        ('taxa_cartao_credito', '0.01275', 'Taxa Cartao Credito (1,275%)', 'taxas'),
        ('taxa_cartao_debito',  '0.002225', 'Taxa Cartao Debito (0,2225%)', 'taxas'),
        ('perc_fp_franquia',   '0.012222', 'Fundo de Promocao Franquia (1,2222%)', 'franquia'),
        ('lr_pis',   '0.0165', 'PIS Lucro Real (1,65%)', 'lucro_real'),
        ('lr_cofins', '0.076', 'COFINS Lucro Real (7,60%)', 'lucro_real'),
        ('lr_irpj',  '0.15',  'IRPJ Lucro Real (15%)', 'lucro_real'),
        ('lr_csll',  '0.09',  'CSLL Lucro Real (9%)', 'lucro_real'),
        ('lr_irpj_adicional', '0.10', 'IRPJ Adicional (10%)', 'lucro_real'),
        ('lr_irpj_adicional_threshold', '20000.0', 'Limite IRPJ Adicional (R$20.000)', 'lucro_real'),
    ]
    for key, value, desc, cat in defaults:
        if not Parameter.query.filter_by(key=key).first():
            db.session.add(Parameter(key=key, value=value, description=desc, category=cat))

    if SimplesNacionalTable.query.count() == 0:
        for mn, mx, rate in [
            (0, 120000, 0.04), (120000.01, 240000, 0.0547), (240000.01, 360000, 0.0684),
            (360000.01, 480000, 0.0754), (480000.01, 600000, 0.076), (600000.01, 720000, 0.0828),
            (720000.01, 840000, 0.0836), (840000.01, 960000, 0.0845), (960000.01, 1080000, 0.0903),
            (1080000.01, 1200000, 0.0912), (1200000.01, 1320000, 0.0995), (1320000.01, 1440000, 0.1004),
            (1440000.01, 1560000, 0.1013), (1560000.01, 1680000, 0.1023), (1680000.01, 1800000, 0.1032),
            (1800000.01, 1920000, 0.1123), (1920000.01, 2040000, 0.1132), (2040000.01, 2160000, 0.1142),
            (2160000.01, 2280000, 0.1151), (2280000.01, 4800000, 0.1161),
        ]:
            db.session.add(SimplesNacionalTable(min_revenue=mn, max_revenue=mx, rate=rate))

    if Store.query.count() == 0:
        db.session.add(Store(name='Loja Modelo', city='Cidade'))

    db.session.commit()


# ── App factory ──────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dre-tiptop-secret-2024-change-me')

    # PostgreSQL no Render/Supabase, SQLite local
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Supabase/Render envia 'postgres://' mas SQLAlchemy 2.x exige 'postgresql://'
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        basedir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(basedir, 'dre.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    # Cria tabelas e dados padrão dentro do contexto do app
    with app.app_context():
        db.create_all()
        _seed_defaults()

    login_manager = LoginManager(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Por favor, faca login para acessar esta pagina.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ── Decorators ────────────────────────────────────────────────────────────

    def admin_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.is_admin():
                abort(403)
            return f(*args, **kwargs)
        return decorated

    def manager_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.is_manager():
                abort(403)
            return f(*args, **kwargs)
        return decorated

    # ── Context processors ────────────────────────────────────────────────────

    @app.context_processor
    def inject_globals():
        return {
            'MONTHS': ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'],
            'now': datetime.now(),
        }

    @app.template_filter('calc_dre')
    def calc_dre_filter(entry):
        return calculate_dre(entry)

    @app.template_filter('brl')
    def brl_filter(value):
        try:
            return f'R$ {float(value):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        except (ValueError, TypeError):
            return 'R$ 0,00'

    @app.template_filter('pct')
    def pct_filter(value):
        try:
            return f'{float(value):.2f}%'
        except (ValueError, TypeError):
            return '0,00%'

    # ── Auth routes ───────────────────────────────────────────────────────────

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            remember = request.form.get('remember') == 'on'
            user = User.query.filter(
                (User.username == username) | (User.email == username)
            ).first()
            if user and user.check_password(password) and user.is_active:
                login_user(user, remember=remember)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard'))
            flash('Usuário ou senha inválidos.', 'danger')
        return render_template('auth/login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        # Only allow if no admin exists (first-time setup)
        admin_exists = User.query.filter_by(role='admin').first()
        if admin_exists and not (current_user.is_authenticated and current_user.is_admin()):
            flash('Registro desabilitado. Solicite acesso ao administrador.', 'info')
            return redirect(url_for('login'))
        stores = Store.query.filter_by(is_active=True).all()
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            store_id = request.form.get('store_id') or None
            role = request.form.get('role', 'user')
            if not admin_exists:
                role = 'admin'
            if User.query.filter_by(username=username).first():
                flash('Nome de usuário já existe.', 'danger')
            elif User.query.filter_by(email=email).first():
                flash('E-mail já cadastrado.', 'danger')
            elif len(password) < 6:
                flash('Senha deve ter pelo menos 6 caracteres.', 'danger')
            else:
                user = User(username=username, email=email, role=role,
                            store_id=int(store_id) if store_id else None)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                if not admin_exists:
                    flash('Administrador criado com sucesso! Faça login.', 'success')
                    return redirect(url_for('login'))
                flash(f'Usuário "{username}" criado com sucesso.', 'success')
                return redirect(url_for('admin_users'))
        return render_template('auth/register.html', stores=stores,
                               first_setup=not admin_exists)

    # ── Dashboard ─────────────────────────────────────────────────────────────

    @app.route('/')
    @login_required
    def dashboard():
        year = request.args.get('year', datetime.now().year, type=int)
        if current_user.is_admin():
            stores = Store.query.filter_by(is_active=True).all()
        elif current_user.store_id:
            stores = [current_user.store]
        else:
            stores = []

        store_summaries = []
        for store in stores:
            entries = DREEntry.query.filter_by(store_id=store.id, year=year).order_by(DREEntry.month).all()
            summary = calculate_annual_summary(entries) if entries else None
            store_summaries.append({'store': store, 'summary': summary, 'entry_count': len(entries)})

        years = db.session.query(DREEntry.year).distinct().order_by(DREEntry.year.desc()).all()
        years = [y[0] for y in years] or [datetime.now().year]

        return render_template('dashboard.html', store_summaries=store_summaries,
                               year=year, years=years)

    # ── DRE Entry ─────────────────────────────────────────────────────────────

    @app.route('/dre/novo', methods=['GET', 'POST'])
    @login_required
    def dre_new():
        if current_user.is_admin():
            stores = Store.query.filter_by(is_active=True).all()
        elif current_user.store_id:
            stores = [current_user.store]
        else:
            flash('Você não está vinculado a nenhuma loja.', 'warning')
            return redirect(url_for('dashboard'))

        year = request.args.get('year', datetime.now().year, type=int)
        month = request.args.get('month', datetime.now().month, type=int)
        store_id = request.args.get('store_id', stores[0].id if stores else None, type=int)

        entry = DREEntry.query.filter_by(store_id=store_id, year=year, month=month).first()
        if entry:
            return redirect(url_for('dre_edit', entry_id=entry.id))

        if request.method == 'POST':
            entry = _save_dre_from_form(request.form, None)
            if entry:
                flash('DRE salvo com sucesso!', 'success')
                return redirect(url_for('dre_view', entry_id=entry.id))

        return render_template('dre/form.html', entry=None, stores=stores,
                               year=year, month=month, store_id=store_id)

    @app.route('/dre/<int:entry_id>/editar', methods=['GET', 'POST'])
    @login_required
    def dre_edit(entry_id):
        entry = DREEntry.query.get_or_404(entry_id)
        _check_store_access(entry.store_id)
        stores = Store.query.filter_by(is_active=True).all() if current_user.is_admin() else [current_user.store]

        if request.method == 'POST':
            updated = _save_dre_from_form(request.form, entry)
            if updated:
                flash('DRE atualizado com sucesso!', 'success')
                return redirect(url_for('dre_view', entry_id=updated.id))

        return render_template('dre/form.html', entry=entry, stores=stores,
                               year=entry.year, month=entry.month, store_id=entry.store_id)

    @app.route('/dre/<int:entry_id>')
    @login_required
    def dre_view(entry_id):
        entry = DREEntry.query.get_or_404(entry_id)
        _check_store_access(entry.store_id)
        result = calculate_dre(entry)
        return render_template('dre/view.html', entry=entry, result=result)

    @app.route('/dre/<int:entry_id>/deletar', methods=['POST'])
    @login_required
    def dre_delete(entry_id):
        entry = DREEntry.query.get_or_404(entry_id)
        _check_store_access(entry.store_id)
        if not current_user.is_manager():
            abort(403)
        db.session.delete(entry)
        db.session.commit()
        flash('DRE removido.', 'info')
        return redirect(url_for('dashboard'))

    @app.route('/dre/lista')
    @login_required
    def dre_list():
        year = request.args.get('year', datetime.now().year, type=int)
        store_id = request.args.get('store_id', type=int)

        query = DREEntry.query.filter_by(year=year)
        if not current_user.is_admin():
            query = query.filter_by(store_id=current_user.store_id)
        elif store_id:
            query = query.filter_by(store_id=store_id)

        entries = query.order_by(DREEntry.store_id, DREEntry.month).all()
        stores = Store.query.filter_by(is_active=True).all() if current_user.is_admin() else []
        years = db.session.query(DREEntry.year).distinct().order_by(DREEntry.year.desc()).all()
        years = [y[0] for y in years] or [datetime.now().year]

        return render_template('dre/list.html', entries=entries, year=year,
                               store_id=store_id, stores=stores, years=years)

    @app.route('/dre/anual')
    @login_required
    def dre_annual():
        year = request.args.get('year', datetime.now().year, type=int)
        store_id = request.args.get('store_id', type=int)

        if current_user.is_admin():
            stores = Store.query.filter_by(is_active=True).all()
        else:
            stores = [current_user.store] if current_user.store else []
            store_id = current_user.store_id

        if not store_id and stores:
            store_id = stores[0].id

        store = Store.query.get_or_404(store_id) if store_id else None
        entries = []
        summary = None
        if store:
            _check_store_access(store.id)
            entries = DREEntry.query.filter_by(store_id=store_id, year=year).order_by(DREEntry.month).all()
            summary = calculate_annual_summary(entries)

        years = db.session.query(DREEntry.year).distinct().order_by(DREEntry.year.desc()).all()
        years = [y[0] for y in years] or [datetime.now().year]

        return render_template('dre/annual.html', store=store, stores=stores,
                               summary=summary, entries=entries, year=year,
                               store_id=store_id, years=years)

    # ── Admin – Users ─────────────────────────────────────────────────────────

    @app.route('/admin')
    @login_required
    @admin_required
    def admin_index():
        total_users = User.query.count()
        total_stores = Store.query.count()
        total_entries = DREEntry.query.count()
        return render_template('admin/index.html', total_users=total_users,
                               total_stores=total_stores, total_entries=total_entries)

    @app.route('/admin/usuarios')
    @login_required
    @admin_required
    def admin_users():
        users = User.query.order_by(User.username).all()
        return render_template('admin/users.html', users=users)

    @app.route('/admin/usuarios/novo', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_user_new():
        return redirect(url_for('register'))

    @app.route('/admin/usuarios/<int:user_id>/editar', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_user_edit(user_id):
        user = User.query.get_or_404(user_id)
        stores = Store.query.filter_by(is_active=True).all()
        if request.method == 'POST':
            user.username = request.form.get('username', user.username).strip()
            user.email = request.form.get('email', user.email).strip()
            user.role = request.form.get('role', 'user')
            store_id = request.form.get('store_id')
            user.store_id = int(store_id) if store_id else None
            user.is_active = request.form.get('is_active') == 'on'
            new_pw = request.form.get('password', '')
            if new_pw:
                if len(new_pw) < 6:
                    flash('Senha deve ter pelo menos 6 caracteres.', 'danger')
                    return render_template('admin/user_edit.html', user=user, stores=stores)
                user.set_password(new_pw)
            db.session.commit()
            flash('Usuário atualizado.', 'success')
            return redirect(url_for('admin_users'))
        return render_template('admin/user_edit.html', user=user, stores=stores)

    @app.route('/admin/usuarios/<int:user_id>/deletar', methods=['POST'])
    @login_required
    @admin_required
    def admin_user_delete(user_id):
        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            flash('Você não pode remover sua própria conta.', 'danger')
            return redirect(url_for('admin_users'))
        db.session.delete(user)
        db.session.commit()
        flash('Usuário removido.', 'info')
        return redirect(url_for('admin_users'))

    # ── Admin – Stores ────────────────────────────────────────────────────────

    @app.route('/admin/lojas')
    @login_required
    @admin_required
    def admin_stores():
        stores = Store.query.order_by(Store.name).all()
        return render_template('admin/stores.html', stores=stores)

    @app.route('/admin/lojas/nova', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_store_new():
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            city = request.form.get('city', '').strip()
            if not name:
                flash('Nome da loja é obrigatório.', 'danger')
            else:
                store = Store(name=name, city=city)
                db.session.add(store)
                db.session.commit()
                flash(f'Loja "{name}" criada.', 'success')
                return redirect(url_for('admin_stores'))
        return render_template('admin/store_form.html', store=None)

    @app.route('/admin/lojas/<int:store_id>/editar', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_store_edit(store_id):
        store = Store.query.get_or_404(store_id)
        if request.method == 'POST':
            store.name = request.form.get('name', store.name).strip()
            store.city = request.form.get('city', '').strip()
            store.is_active = request.form.get('is_active') == 'on'
            db.session.commit()
            flash('Loja atualizada.', 'success')
            return redirect(url_for('admin_stores'))
        return render_template('admin/store_form.html', store=store)

    # ── Admin – Parameters ────────────────────────────────────────────────────

    @app.route('/admin/parametros', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_params():
        if request.method == 'POST':
            for key in request.form:
                if key.startswith('param_'):
                    param_key = key[6:]
                    p = Parameter.query.filter_by(key=param_key).first()
                    if p:
                        p.value = request.form[key].replace(',', '.')
            db.session.commit()
            flash('Parâmetros salvos com sucesso.', 'success')
            return redirect(url_for('admin_params'))

        params = Parameter.query.order_by(Parameter.category, Parameter.key).all()
        by_category = {}
        for p in params:
            by_category.setdefault(p.category, []).append(p)
        return render_template('admin/params.html', by_category=by_category)

    @app.route('/admin/simples', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_simples():
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'update':
                row_id = int(request.form.get('id'))
                row = SimplesNacionalTable.query.get(row_id)
                if row:
                    row.min_revenue = float(request.form.get('min_revenue', 0).replace(',', '.'))
                    row.max_revenue = float(request.form.get('max_revenue', 0).replace(',', '.'))
                    row.rate = float(request.form.get('rate', 0).replace(',', '.')) / 100
                    db.session.commit()
                    flash('Faixa atualizada.', 'success')
            elif action == 'add':
                row = SimplesNacionalTable(
                    min_revenue=float(request.form.get('min_revenue', 0).replace(',', '.')),
                    max_revenue=float(request.form.get('max_revenue', 0).replace(',', '.')),
                    rate=float(request.form.get('rate', 0).replace(',', '.')) / 100,
                )
                db.session.add(row)
                db.session.commit()
                flash('Faixa adicionada.', 'success')
            elif action == 'delete':
                row_id = int(request.form.get('id'))
                row = SimplesNacionalTable.query.get(row_id)
                if row:
                    db.session.delete(row)
                    db.session.commit()
                    flash('Faixa removida.', 'info')
            return redirect(url_for('admin_simples'))

        table = SimplesNacionalTable.query.order_by(SimplesNacionalTable.min_revenue).all()
        return render_template('admin/simples.html', table=table)

    # ── Error handlers ────────────────────────────────────────────────────────

    @app.route('/health')
    def health():
        from flask import jsonify
        try:
            user_count = User.query.count()
            store_count = Store.query.count()
            return jsonify(status='ok', users=user_count, stores=store_count), 200
        except Exception as e:
            return jsonify(status='error', message=str(e)), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _check_store_access(store_id):
        if current_user.is_admin():
            return
        if current_user.store_id != store_id:
            abort(403)

    def _save_dre_from_form(form, entry):
        """Create or update a DREEntry from POST form data."""
        store_id = int(form.get('store_id', 0))
        if not current_user.is_admin() and current_user.store_id != store_id:
            abort(403)

        year = int(form.get('year', datetime.now().year))
        month = int(form.get('month', datetime.now().month))

        if entry is None:
            existing = DREEntry.query.filter_by(store_id=store_id, year=year, month=month).first()
            if existing:
                flash('Já existe um DRE para esta loja/mês/ano. Editando existente.', 'info')
                entry = existing
            else:
                entry = DREEntry(store_id=store_id, year=year, month=month,
                                 created_by=current_user.id)
                db.session.add(entry)
        else:
            entry.year = year
            entry.month = month
            entry.store_id = store_id

        def fv(key, default=0.0):
            val = form.get(key, '').replace(',', '.').strip()
            try:
                return float(val) if val else default
            except ValueError:
                return default

        def iv(key, default=0):
            val = form.get(key, '').strip()
            try:
                return int(float(val)) if val else default
            except ValueError:
                return default

        entry.regime_tributario = form.get('regime_tributario', 'simples')
        entry.receita_12_meses = fv('receita_12_meses') or None

        # Gerenciais
        entry.meta_vendas = fv('meta_vendas')
        entry.pecas_vendidas = iv('pecas_vendidas')
        entry.atendimentos = iv('atendimentos')
        entry.markup = fv('markup')
        entry.estoque_qtd = iv('estoque_qtd')
        entry.estoque_valor = fv('estoque_valor')

        # Faturamento
        entry.fat_produtos = fv('fat_produtos')
        entry.fat_outros = fv('fat_outros')

        # DV Gerais
        entry.inadimplencia = fv('inadimplencia')
        entry.marketing_local = fv('marketing_local')
        cc = form.get('cartao_credito_manual', '').strip()
        entry.cartao_credito_manual = float(cc.replace(',', '.')) if cc else None
        cd = form.get('cartao_debito_manual', '').strip()
        entry.cartao_debito_manual = float(cd.replace(',', '.')) if cd else None
        entry.embalagens_frete = fv('embalagens_frete')
        entry.fretes_extras = fv('fretes_extras')
        entry.despesas_bancarias = fv('despesas_bancarias')
        entry.dv_gerais_outros1 = fv('dv_gerais_outros1')
        entry.dv_gerais_outros2 = fv('dv_gerais_outros2')

        # DV Pessoal
        entry.salario_gerente = fv('salario_gerente')
        entry.salario_vendedores = fv('salario_vendedores')
        entry.salario_supervisora = fv('salario_supervisora')
        entry.salario_escritorio = fv('salario_escritorio')
        entry.gincanas_premios = fv('gincanas_premios')
        entry.fgts = fv('fgts')
        entry.inss = fv('inss')
        entry.contrib_sindical = fv('contrib_sindical')
        entry.encargos_outros = fv('encargos_outros')
        entry.vale_transporte = fv('vale_transporte')
        entry.vale_refeicao = fv('vale_refeicao')
        entry.beneficios_outros = fv('beneficios_outros')
        entry.decimo_terceiro = fv('decimo_terceiro')
        entry.ferias = fv('ferias')
        entry.rescisoes = fv('rescisoes')
        entry.pessoal_outros1 = fv('pessoal_outros1')
        entry.pessoal_outros2 = fv('pessoal_outros2')

        # CMV
        entry.cmv_tdb = fv('cmv_tdb')
        entry.cmv_terceiros = fv('cmv_terceiros')
        entry.royalties = fv('royalties')
        entry.diferencial_icms = fv('diferencial_icms')

        # Custos Fixos
        entry.pro_labore = fv('pro_labore')
        entry.contabilidade = fv('contabilidade')
        entry.limpeza = fv('limpeza')
        entry.software_microvix = fv('software_microvix')
        entry.ecad = fv('ecad')
        entry.sonorizacao = fv('sonorizacao')
        entry.pos_tef = fv('pos_tef')
        entry.seguros = fv('seguros')
        entry.manutencao_geral = fv('manutencao_geral')
        entry.giver_omnichannel = fv('giver_omnichannel')
        entry.intranet = fv('intranet')
        entry.qlik_sense = fv('qlik_sense')
        entry.internet = fv('internet')
        entry.telefonia = fv('telefonia')
        entry.aluguel_percentual = fv('aluguel_percentual')
        entry.aluguel_minimo = fv('aluguel_minimo')
        entry.condominio = fv('condominio')
        entry.fp_shopping = fv('fp_shopping')
        entry.energia_eletrica = fv('energia_eletrica')
        entry.ar_condicionado = fv('ar_condicionado')
        entry.agua = fv('agua')
        entry.iptu = fv('iptu')
        entry.outros_impostos_municipais = fv('outros_impostos_municipais')
        entry.papelaria = fv('papelaria')
        entry.provisao_inventario = fv('provisao_inventario')
        entry.uniformes = fv('uniformes')
        entry.outros_gastos = fv('outros_gastos')
        entry.viagens_treinamentos = fv('viagens_treinamentos')
        entry.cf_outros1 = fv('cf_outros1')
        entry.cf_outros2 = fv('cf_outros2')

        # Finais
        entry.retirada_socios = fv('retirada_socios')
        entry.desconto_percent = fv('desconto_percent')
        entry.updated_at = datetime.utcnow()

        db.session.commit()
        return entry

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
