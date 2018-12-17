from netmiko import ConnectHandler
from datetime import datetime
import re
from telnetlib import Telnet
import time


class ConfigTelnet:
    def __init__(self, ip, username, password, secret, device_type, hostname):
        credential = {
                'ip' : ip,
                'username' : username,
                'password' : password,
                'device_type' : device_type,
                'hostname' : hostname,
                'secret' : secret
                }

        self.credential = credential
        self.telnet = Telnet(credential['ip'])
        self.cisco_prompt = credential['hostname']+'#'
        self.juniper_prompt = credential['username']+'@'+credential['hostname']
        self.juniper_prompt_oper = credential['username']+'@'+credential['hostname']+'>'
        self.juniper_prompt_conf = credential['username']+'@'+credential['hostname']+'#'

        ## device init ##
        if credential['device_type'] == 'Cisco':
            self.cisco_init()
        elif credential['device_type'] == 'Juniper':
            self.juniper_init()

    def cisco_init(self):
        userpass = self.credential['username']+'\n'+self.credential['password']+'\n'
        enable = 'en'+'\n'+self.credential['secret']+'\n'
        self.telnet.read_until(b'Username')
        self.telnet.write(userpass.encode('ascii'))
        self.telnet.write(enable.encode('ascii'))
        self.telnet.read_until(self.cisco_prompt.encode('ascii'))

        #remove cisco terminal length
        self.telnet.write(b'ter leng 0\n')
        self.telnet.read_until(self.cisco_prompt.encode('ascii'))

    def juniper_init(self):
        self.telnet.read_until(b'login:')
        self.telnet.write(self.credential['username'].encode('ascii')+b'\n')
        self.telnet.read_until(b'Password:')
        self.telnet.write(self.credential['password'].encode('ascii')+b'\n')
        self.telnet.read_until(self.juniper_prompt.encode('ascii'))
        self.telnet.write(b'cli\n')
        self.telnet.read_until(self.juniper_prompt_oper.encode('ascii'))

    def juniper_conf_backup(self):
        result = dict()
        self.telnet.write(b'show configuration | no-more\n')
        self.telnet.read_until(b'\n')
        self.telnet.read_until(b'\n')
        backup = self.telnet.read_until(self.juniper_prompt_oper.encode('ascii'))
        backup = backup.replace('\n','\r')
        backup = backup.replace(self.juniper_prompt_oper, '')

        result['configuration'] = backup
        result['timestamp'] = str(datetime.now())
        result['address'] = self.credential['ip']
        result['hostname'] = self.credential['hostname']
        result['status'] = 'SUCCESS'

        return result

    def juniper_conf_restore(self, backup):
        result = dict()
        self.telnet.write(b'start shell\n')
        self.telnet.read_until(b'%',1)
        self.telnet.write(b'cat <<"EOF" > /var/home/%s/restore-config.conf\r%s\r"EOF"\r' % (self.credential['username'].encode('ascii'), backup.encode('ascii')))

        self.telnet.read_until(b'%')
        self.telnet.write(b'exit\n')
        self.telnet.read_until(self.juniper_prompt_oper.encode('ascii'))
        self.telnet.write(b'configure\n')
        self.telnet.read_until(self.juniper_prompt_conf.encode('ascii'))
        self.telnet.write(b'load override /var/home/%s/restore-config.conf\n' % self.credential['username'].encode('ascii'))
        self.telnet.read_until(self.juniper_prompt_conf.encode('ascii'))
        self.telnet.write(b'commit\n')
        self.telnet.read_until(b'commit complete')

        result['address'] = self.credential['ip']
        result['status'] = 'SUCCESS'
        result['timestamp'] = str(datetime.now())
        result['hostname'] = self.credential['hostname']

        return result

    def cisco_conf_backup(self):
        result = dict()
        self.telnet.write(b'show running-config\n')
        self.telnet.read_until(b'Building configuration...')

        #get entire configuration
        backup =  self.telnet.read_until(self.cisco_prompt.encode('ascii'))
        result['configuration'] = backup.replace('\n','\r')
        result['timestamp'] = str(datetime.now())
        result['address'] = self.credential['ip']
        result['status'] = 'SUCCESS'
        result['hostname'] = self.credential['hostname']

        return result

    def cisco_conf_restore(self, backup):
        result = dict()
        configs = backup.split('\r')
        self.telnet.write(b'tclsh\r')
        self.telnet.write(b'puts [open restore-config.conf w+] {\r')
        for config in configs:
            self.telnet.read_until(b'+>')
            self.telnet.write(config.encode('ascii')+b'\r')
        self.telnet.read_until(b'+>')
        self.telnet.write(b'}\r')
        self.telnet.read_until(b'(tcl)')
        self.telnet.write(b'tclquit\r')
        hasil = self.telnet.read_until(self.prompt.encode('ascii'))

        #execute restore command
        self.telnet.write(b'configure replace flash:restore-config.conf\r')
        time.sleep(1)
        self.telnet.write(b'y\r')

        result['address'] = self.credential['ip']
        result['status'] = 'SUCCESS'
        result['timestamp'] = str(datetime.now())
        result['hostname'] = self.credential['hostname']
        
        return result

    def close(self):
        self.telnet.close()
        

class ConfigSSH:
    def __init__(self, ip, device_type, username, password, secret, hostname):
        credential = {
                'ip' : ip,
                'device_type' : device_type,
                'username' : username,
                'password' : password,
                'secret' : secret,
                }
        
        self.hostname = hostname
        self.credential = credential
        self.conn = ConnectHandler(**credential)

    def close(self):
        self.conn.disconnect()

    '''
    def find_hostname(self):
        prompt = self.conn.find_prompt()
        if self.credential['device_type'] == 'cisco_ios':
            if '>' in prompt:
                hostname = prompt.replace('>','')
                return hostname
            elif '#' in prompt:
                hostname = prompt.replace('#','')
                return hostname
        elif self.credential['device_type'] == 'juniper_junos':
            hostname_search = re.search(r'\S+@(\S+)[>#]', self.conn.find_prompt())
            hostname = hostname_search.group(1)
            return hostname
    '''

    def cisco_conf_backup(self):
        cisco_conf = dict()
        #find hostname
        cisco_conf['hostname'] = self.hostname

        #if there is any secret password
        if self.credential['secret'] != None:
            self.conn.enable()
        
        #grab current config
        config_output = self.conn.send_command('show running-config')
        cisco_conf['configuration'] = config_output.replace('\n','\r')
        cisco_conf['timestamp'] = str(datetime.now()) 
        cisco_conf['address'] = self.credential['ip']
        cisco_conf['status'] = 'SUCCESS' 

        return cisco_conf
    
    def juniper_conf_backup(self):
        juniper_conf = dict()
        #find hostname
        juniper_conf['hostname'] = self.hostname

        #grab current config
        config_output = self.conn.send_command('show configuration')
        juniper_conf['configuration'] = config_output.replace('\n','\r')
        juniper_conf['timestamp'] = str(datetime.now())
        juniper_conf['address'] = self.credential['ip']
        juniper_conf['status'] = 'SUCCESS'

        return juniper_conf

    def cisco_conf_restore(self, config):
        cisco_conf = dict()
        if self.credential['secret'] != None:
            self.conn.enable()
        
        #create tcl script on router
        self.conn.send_command('tclsh', expect_string='')
        self.conn.send_command('puts [open restore-config.conf w+] {\r%s}' % config)
        self.conn.send_command('tclquit', expect_string='')

        #restore config to system
        self.conn.send_command('configure replace flash:restore-config.conf\ry\r\r')
        cisco_conf['hostname'] = self.hostname
        cisco_conf['address'] = self.credential['ip']
        cisco_conf['status'] = 'SUCCESS'
        cisco_conf['timestamp'] = str(datetime.now())
        return cisco_conf

    def juniper_conf_restore(self, config):
        juniper_conf = dict()

        #create file for restore configuration
        self.conn.send_command('start shell', expect_string='')
        self.conn.send_command('cat <<"EOF" > /var/home/%s/restore-config.conf\r%s\r"EOF"' % (self.credential['username'], config))
        self.conn.send_command('cli', expect_string='')

        #restore config to system
        self.conn.send_config_set(['load override /var/home/%s/restore-config.conf' % self.credential['username'],'commit'])
        juniper_conf['hostname'] = self.hostname
        juniper_conf['address'] = self.credential['ip']
        juniper_conf['restore_status'] = 'SUCCESS'
        juniper_conf['timestamp'] = str(datetime.now())

        return juniper_conf

