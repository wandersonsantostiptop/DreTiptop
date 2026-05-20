"""Initialize the database with default data."""
from app import app
from models import db, User, Store, Parameter, SimplesNacionalTable


def init_db():
    with app.app_context():
        db.create_all()
        print("[OK] Tabelas criadas.")

        # ── Default parameters ──────────────────────────────────────────────
        defaults = [
            # Taxas de cartão
            ('taxa_cartao_credito', '0.01275', 'Taxa retida pela operadora – Crédito (1,275%)', 'taxas'),
            ('taxa_cartao_debito',  '0.002225', 'Taxa retida pela operadora – Débito (0,2225%)', 'taxas'),
            # Fundo de promoção
            ('perc_fp_franquia', '0.012222', 'Fundo de Promoção da Franquia (1,2222%)', 'franquia'),
            # Lucro Real
            ('lr_pis',   '0.0165',  'PIS – Lucro Real (1,65%)', 'lucro_real'),
            ('lr_cofins', '0.076',  'COFINS – Lucro Real (7,60%)', 'lucro_real'),
            ('lr_irpj',  '0.15',   'IRPJ – Lucro Real (15%)', 'lucro_real'),
            ('lr_csll',  '0.09',   'CSLL – Lucro Real (9%)', 'lucro_real'),
            ('lr_irpj_adicional', '0.10', 'IRPJ Adicional – Lucro Real (10%)', 'lucro_real'),
            ('lr_irpj_adicional_threshold', '20000.0',
             'Limite mensal para adicional IRPJ (R$ 20.000)', 'lucro_real'),
        ]
        for key, value, desc, cat in defaults:
            if not Parameter.query.filter_by(key=key).first():
                db.session.add(Parameter(key=key, value=value, description=desc, category=cat))
        print("[OK] Parâmetros padrão inseridos.")

        # ── Simples Nacional – Anexo I (Comércio) ───────────────────────────
        simples_table = [
            (0,          120000,    0.0400),
            (120000.01,  240000,    0.0547),
            (240000.01,  360000,    0.0684),
            (360000.01,  480000,    0.0754),
            (480000.01,  600000,    0.0760),
            (600000.01,  720000,    0.0828),
            (720000.01,  840000,    0.0836),
            (840000.01,  960000,    0.0845),
            (960000.01,  1080000,   0.0903),
            (1080000.01, 1200000,   0.0912),
            (1200000.01, 1320000,   0.0995),
            (1320000.01, 1440000,   0.1004),
            (1440000.01, 1560000,   0.1013),
            (1560000.01, 1680000,   0.1023),
            (1680000.01, 1800000,   0.1032),
            (1800000.01, 1920000,   0.1123),
            (1920000.01, 2040000,   0.1132),
            (2040000.01, 2160000,   0.1142),
            (2160000.01, 2280000,   0.1151),
            (2280000.01, 4800000,   0.1161),
        ]
        if SimplesNacionalTable.query.count() == 0:
            for mn, mx, rate in simples_table:
                db.session.add(SimplesNacionalTable(min_revenue=mn, max_revenue=mx, rate=rate))
        print("[OK] Tabela Simples Nacional inserida.")

        # ── Default store ───────────────────────────────────────────────────
        if Store.query.count() == 0:
            db.session.add(Store(name='Loja Modelo', city='Cidade'))
        print("[OK] Loja padrão criada.")

        db.session.commit()
        print("\n[DONE] Banco de dados inicializado!")
        print("\nAcesse http://localhost:5000 e crie o primeiro usuário admin.")


if __name__ == '__main__':
    init_db()
