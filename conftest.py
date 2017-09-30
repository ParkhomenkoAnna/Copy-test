import pytest
import json
def pytest_addoption(parser):
    parser.addoption("--user", action="store",  default="anna", help="Username")
    parser.addoption("--passwd", action="store", default="tester",  help="Password")
    parser.addoption("--ip_addr1", action="store",   default=False,help="IP-address a ESR")
    parser.addoption("--ip_addr2", action="store",  default=False, help="IP-addres a PC")
    parser.addoption("--logging", action="store_true", default=False, help="cli logging")

@pytest.fixture(scope="session")
def read_patterns(request):
   with open('patterns.json') as json_data:
        template = json.load(json_data)
        return(template)
