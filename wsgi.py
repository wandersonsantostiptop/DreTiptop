import sys
import os

# Aponte para a pasta da sua aplicação no PythonAnywhere
# Substitua SEU_USUARIO pelo seu usuário do PythonAnywhere
project_home = '/home/SEU_USUARIO/dre_app'

if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.chdir(project_home)

from app import app as application  # noqa
