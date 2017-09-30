import re
import sys
import json
import pytest
import pexpect
import subprocess
from hamcrest import *

USER = pytest.config.getoption("--user")
PASSWORD = pytest.config.getoption("--passwd")
IP_ADDR = pytest.config.getoption("--ip_addr1")
IP_ADDR2 = pytest.config.getoption("--ip_addr2")
LOG = pytest.config.getoption("--logging")
MODEL="ESR-100"
VERSION="1.4.0"
PROTOCOLS= ["tftp", "ftp", "sftp", "scp"]
tftp_dir="/srv/tftp"

@pytest.fixture(scope="session")
def execute_cmd(cmd,connection=None, time=40):
    if connection==None:
        output= subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        return output.stdout.read().decode('utf-8')
    else:
        if VERSION == "1.0.9":
            connection.sendline(cmd.replace("system:", "fs://"))
            connection.expect('\w+#|\w+-\d+#|\d+v#|(config\S+)#', timeout=time)
        else:
            connection.sendline(cmd)
            connection.expect('\w+#|\w+-\d+#|esr-\d+v#|(config\S+)#', timeout=time)
        return connection.before

@pytest.yield_fixture(scope="session")
def config_pc():
    execute_cmd("service tftpd-hpa start")
    execute_cmd( "mkdir {}/test".format(tftp_dir))
    execute_cmd("chmod 777 {}/test".format(tftp_dir))
    execute_cmd("ln -s {}/test /home/{}/test".format(tftp_dir, USER))
    execute_cmd("cd  {}/test;touch ./tftp-licence ./ftp-licence ./sftp-licence ./scp-licence".format(tftp_dir))
    execute_cmd("cp ./test_data/{}.uboot {}/test/{}.uboot".format(MODEL, tftp_dir, MODEL))
    if VERSION == "1.0.9":
        for prot in PROTOCOLS:
            execute_cmd("cp ./test_data/{}.kernel {}/test/{}-esr.firmware".format(MODEL, tftp_dir, prot))
    yield
    execute_cmd( "rm -rf /home/{}/test; rm -rf {}/test".format(USER, tftp_dir))

@pytest.fixture(scope="session")
def connect_to_esr():
    global connection
    global MODEL
    global VERSION
    connection=pexpect.spawn ('telnet {}'.format(IP_ADDR))
    if LOG:
        connection.logfile =sys.stdout
    connection.delaybeforesend = 1
    connection.expect (': ' )
    connection.sendline ('admin')
    connection.expect ('Password:', timeout=15)
    connection.sendline ('password')
    connection.expect('#', timeout=15)
    connection.sendline ('terminal datadump')
    connection.expect('#', timeout=15)
    output=execute_cmd('show system', connection)
    string = re.findall("\w+-\S+(?= Service Router)",output)
    MODEL = string[0]
    output=execute_cmd('show version', connection)
    string = re.findall("\d+.\d+.\d+(?= build)",output)
    VERSION = string[0]

@pytest.mark.usefixtures("config_pc")
@pytest.mark.usefixtures("connect_to_esr")
class TestINFO:
    def test(self, read_patterns):
        print()
        print("*" * 80)
        print(" " * 35 + MODEL)
        print(" " * 36 + VERSION)
        print("*" * 80)

class TestCopyRunConfFromESR:
    @pytest.mark.parametrize("protocols", ["tftp", "ftp", "sftp", "scp"])
    def test(self, protocols, read_patterns):
        if protocols == "tftp":
            cmd = 'copy system:running-config tftp://{}:/test/tftp-running-config'.format(IP_ADDR2)
        else:
            cmd = 'copy system:running-config {}://{}:{}@{}:/test/{}-running-config'.format(protocols,USER, PASSWORD, IP_ADDR2, protocols)
        string = execute_cmd(cmd, connection)
        for pattern in read_patterns("copy run-conf")[protocols]:
            assert_that(string, matches_regexp(pattern))

class TestCopyCandidatConfigToESR:
    @pytest.mark.parametrize("protocols", ["tftp", "ftp", "sftp", "scp"])
    def test(self, protocols, read_patterns):
        if protocols == "tftp":
            cmd = 'copy tftp://{}:/test/tftp-running-config system:candidate-config'.format(IP_ADDR2)
        else:
            cmd = 'copy {}://{}:{}@{}:/test/{}-running-config system:candidate-config'.format(protocols,USER, PASSWORD,
                                                                                                IP_ADDR2,protocols)
        string = execute_cmd(cmd, connection)
        for pattern in read_patterns("copy candidat-config")[protocols]:
            assert_that(string, matches_regexp(pattern))

@pytest.mark.skipif('VERSION=="1.0.9"', reason="Copy firmware from ESR | ESR-10 and ESR-12V v1.0.9 can't copy firmware to PC")
class TestCopyFirmwareFromESR:
    @pytest.mark.parametrize("protocols", ["tftp", "ftp", "sftp", "scp"])
    def test(self, protocols, read_patterns):
        if protocols == "tftp":
            cmd = 'copy system:firmware tftp://{}:/test/tftp-esr.firmware'.format(IP_ADDR2)
        else:
            cmd = 'copy system:firmware {}://{}:{}@{}:/test/{}-esr.firmware'.format(protocols, USER, PASSWORD,
                                                                                                IP_ADDR2, protocols)
        string = execute_cmd(cmd, connection,50)
        for pattern in read_patterns("copy firmware from esr")[protocols]:
            assert_that(string,  matches_regexp(pattern))

class TestCopyFirmwareToESR:
    def test_tftp(self, read_patterns):
        cmd='copy tftp://{}:/test/tftp-esr.firmware system:firmware '.format(IP_ADDR2)
        string = execute_cmd(cmd, connection,90)
        for pattern in read_patterns("copy firmware to esr")["tftp"]:
            assert_that(string,  matches_regexp(pattern))

    def test_show_bootvar_tftp(self, read_patterns):
        cmd = 'show bootvar'
        string = execute_cmd(cmd, connection, 15)
        pattern = read_patterns("show_bootvar")
        assert_that(string, is_not(matches_regexp(pattern)))

    def test_ftp(self, read_patterns):
        cmd='copy ftp://{}:{}@{}:/test/ftp-esr.firmware system:firmware '.format(USER,PASSWORD,IP_ADDR2)
        string = execute_cmd(cmd, connection,90)
        for pattern in read_patterns("copy firmware to esr")["ftp"]:
            assert_that(string,  matches_regexp(pattern))

    def test_show_bootvar_ftp(self, read_patterns):
        cmd = 'show bootvar'
        string = execute_cmd(cmd, connection, 15)
        pattern = read_patterns("show_bootvar")
        assert_that(string, is_not(matches_regexp(pattern)))

    def test_sftp(self, read_patterns):
        cmd='copy sftp://{}:{}@{}:/test/sftp-esr.firmware system:firmware '.format(USER,PASSWORD,IP_ADDR2)
        string = execute_cmd(cmd, connection,90)
        for pattern in read_patterns("copy firmware to esr")["sftp"]:
            assert_that(string,  matches_regexp(pattern))


    def test_show_bootvar_sftp(self, read_patterns):
        cmd = 'show bootvar'
        string = execute_cmd(cmd, connection, 15)
        pattern = read_patterns("show_bootvar")
        assert_that(string, is_not(matches_regexp(pattern)))

    def test_scp(self, read_patterns):
        cmd='copy scp://{}:{}@{}:/test/scp-esr.firmware system:firmware '.format(USER,PASSWORD,IP_ADDR2)
        string = execute_cmd(cmd, connection,90)
        for pattern in read_patterns("copy firmware to esr")["scp"]:
            assert_that(string,  matches_regexp(pattern))

    def test_show_bootvar_scp(self, read_patterns):
        cmd = 'show bootvar'
        string = execute_cmd(cmd, connection, 15)
        pattern = read_patterns("show_bootvar")
        assert_that(string, is_not(matches_regexp(pattern)))

@pytest.mark.skipif('VERSION=="1.0.9"', reason="Copy uboot from ESR    | ESR-10 and ESR-12V v1.0.9 can't copy boot to PC")
class TestCopyBootFromESR:
    @pytest.mark.parametrize("protocols", ["tftp", "ftp", "sftp", "scp"])
    def test(self, protocols, read_patterns):
        if protocols == "tftp":
            cmd='copy system:boot tftp://{}:/test/tftp-esr.uboot'.format(IP_ADDR2)
        else:
            cmd = 'copy system:boot {}://{}:{}@{}:/test/{}-esr.uboot'.format(protocols, USER, PASSWORD,
                                                                                                IP_ADDR2, protocols)
        string = execute_cmd(cmd, connection)
        for pattern in read_patterns("copy uboot from esr")[protocols]:
            assert_that(string,  matches_regexp(pattern))

@pytest.mark.skipif('VERSION=="1.0.9"', reason="Copy uboot to ESR      | ESR-10 and ESR-12V v1.0.9 can't copy boot from PC")
class TestCopyBootToESR:
    @pytest.mark.parametrize("protocols", ["tftp", "ftp", "sftp", "scp"])
    def test(self, protocols, read_patterns):
        if protocols == "tftp":
            cmd='copy tftp://{}:/test/{}.uboot system:boot'.format(IP_ADDR2, MODEL)
        else:
            cmd = 'copy {}://{}:{}@{}:/test/{}.uboot system:boot'.format(protocols,USER, PASSWORD, IP_ADDR2, MODEL)
        string = execute_cmd(cmd, connection)
        for pattern in read_patterns("copy uboot to esr")[protocols]:
            assert_that(string,  matches_regexp(pattern))

class TestCopyLicenceToESR:
    @pytest.mark.parametrize("protocols", ["tftp", "ftp", "sftp", "scp"])
    def test(self, protocols, read_patterns):
        if protocols == "tftp":
            cmd='copy tftp://{}:/test/tftp-licence system:licence'.format(IP_ADDR2)
        else:
            cmd = 'copy  {}://{}:{}@{}:/test/{}-licence system:licence'.format(protocols, USER, PASSWORD, IP_ADDR2, protocols)
        string = execute_cmd(cmd, connection)
        for pattern in read_patterns("copy licence to esr")[protocols]:
            assert_that(string,  matches_regexp(pattern))

class TestArchive_by_commit:
    @pytest.mark.parametrize("protocols", ["tftp", "ftp", "sftp", "scp"])
    def test(self, protocols, read_patterns):
        execute_cmd("configure", connection,2)
        execute_cmd("no hostname", connection,2)
        execute_cmd("archive", connection,2)
        execute_cmd("by-commit", connection,2)
        if protocols == "tftp":
            execute_cmd("path tftp://{}:/test/tftp-running-config".format(IP_ADDR2),connection)
            execute_cmd("do commit", connection,5)
            execute_cmd("do confirm", connection, 30)
            execute_cmd("exit", connection,2)
            execute_cmd("hostname esr", connection,2)
        elif protocols == "scp":
            execute_cmd("path scp://{}:{}@{}:/home/{}/test/scp-running-config".format(USER, PASSWORD, IP_ADDR2, USER),connection)
        else:
            execute_cmd("path {}://{}:{}@{}:/test/{}-running-config".format(protocols,USER, PASSWORD, IP_ADDR2,protocols),connection)
        execute_cmd("do commit", connection,2)
        execute_cmd("do confirm", connection, 30)
        command_output = execute_cmd("ls {}/test/ -n".format(tftp_dir))
        pattern = read_patterns('archive')[protocols]
        assert_that(command_output, matches_regexp(pattern))

@pytest.mark.skip(reason="Archive by time-period | After applying configuration router is rebooting")
class TestArchive_auto:
    @pytest.mark.parametrize("protocols", ["tftp", "ftp", "sftp", "scp"])
    def test(self, protocols, read_patterns):
        execute_cmd("no by-commit", connection,2)
        execute_cmd("auto", connection,2)
        execute_cmd("time-period 5", connection,2)
        if protocols == "tftp":
            execute_cmd("path tftp://{}:/test/tftp-running-config".format(IP_ADDR2),connection)
        elif protocols == "scp":
            execute_cmd("path scp://{}:{}@{}:/home/{}/test/scp-running-config".format(USER, PASSWORD, IP_ADDR2, USER),connection)
        else:
            execute_cmd("path {}://{}:{}@{}:/test/{}-running-config".format(protocols, USER, PASSWORD, IP_ADDR2, protocols),connection)
        execute_cmd("do commit", connection,5)
        execute_cmd("do confirm", connection, 30)
        command_output = execute_cmd("ls {}/test/ -n".format(tftp_dir))
        pattern = read_patterns('archive')[protocols]
        assert_that(command_output, matches_regexp(pattern))
