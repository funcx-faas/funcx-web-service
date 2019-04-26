from config import cooley_config
import parsl
from parsl.app.app import python_app

parsl.load(cooley_config)

@python_app
def test_app():
    return "hello"

x = test_app()
print(x)
print(x.result())
