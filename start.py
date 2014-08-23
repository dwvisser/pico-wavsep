#!/usr/bin/python

from argparse import ArgumentParser
from os import getcwd
from os.path import abspath, isdir, isfile
from pickle import load, dump
from shutil import copyfile
from subprocess import CalledProcessError, Popen, call
from sys import argv, stdin, stderr
from time import sleep
from urllib import urlencode
from urllib2 import urlopen, HTTPError

import logging

logging.basicConfig(filename='start.log',level=logging.DEBUG)

TIMEOUT_SECONDS = 5
JETTY = 'jetty-distribution-9.2.2.v20140723'
SUCCESS_TEXT = \
	'Mysql configuration rows replaced to reflect a successful installation'

def handle_setup_result(body):
    server_out.write('Here is the response body: ')
    server_out.write(body)
    server_out.write('')

def start_server(args):
	if not isdir(abspath(JETTY)):
		print 'Extracting Jetty from tarball.'
		call(['tar', 'xzf', '{}.tar.gz'.format(JETTY)])
	warfile = 'wavsep.war'
	warpath = '{}/webapps/{}'.format(JETTY, warfile)
	if not isfile(warpath):
		print 'Copying {} to {}/webapps.'.format(warfile, JETTY)
		copyfile(warfile, warpath)
	server = Popen(['java', '-jar', 'start.jar', 
	    'jetty.port={}'.format(args.http_port)], cwd=JETTY,
	    stdout=server_out, stderr=server_err)
	print 'Wavsep server process started with PID {}.'.format(server.pid)
	print 'Server normal messages are being sent to {}'.format(fn_out)
	print 'Server error messages are being sent to {}'.format(fn_err)
	return server

def install_db(server, parser, args, fn_flag):
	print('Waiting a moment for server to initialize.')
	sleep(TIMEOUT_SECONDS)
	installURL = 'http://localhost:{}/wavsep-install/install.jsp'.format(
		args.http_port)
	logging.debug('Sending setup request to {}'.format(installURL))
	setup_params = {'username':args.mysql_user, 'password':args.mysql_pass,
		            'host':args.mysql_host, 'port':args.mysql_port,
		            'wavsep_username':'', 'wavsep_password':''}
	logging.debug('with parameters {}'.format(setup_params))
	try:
		response = urlopen(installURL, urlencode(setup_params), 
							TIMEOUT_SECONDS)
		body = response.read()
		code = response.getcode()
	except HTTPError as http_error:
		body = http_error.reason
		code = http_error.code

	handle_setup_result(body)
	if code == 200:
	    logging.debug(
	    	'Got Success (200) response code from our setup request.')
	    if SUCCESS_TEXT in body:
	        print 'Wavsep setup request completed successully.'
	        logging.debug('Saving install flag.')
	        with open(fn_flag, 'w') as flagfile:
	        	dump(True, flagfile)
	    else:
	    	server.terminate()
	    	parser.error('Expected to see this in response: "{}"'.format(
	    		SUCCESS_TEXT))
	else:
		server.terminate()
		parser.error('Unexpected response code to setup request: {}'.format(
			code))

parser = ArgumentParser(description ='''Launch and configure wavsep.
MySQL Server 5.5 will create a database at ./db''')
parser.add_argument('--mysql-user', type=str, nargs='?', default='root', 
	metavar='USER', help='MySQL Server admin user name (default=root)')
parser.add_argument('--mysql-pass', type=str, nargs='?', default='', const='',
    help='MySQL Server admin password (defaults to no password)', 
    metavar='PASS')
parser.add_argument('--mysql-host', type=str, nargs='?', default='localhost',
	help='MySQL Server host (default=localhost)', metavar='HOST', 
	const='localhost')
parser.add_argument('--mysql-port', type=int, nargs='?', default='3306',
	help='MySQL Server port (default=3306)', const='3306')
parser.add_argument('--http-port', type=int, nargs='?', default='8080',
	help='Wavsep application HTTP port (default=8080)', const='8080')
fn_out = 'pico-wavsep.log'
fn_flag = 'wavsep-installed.txt'
parser.add_argument('--out', type=str, nargs='?', default=fn_out,
	help='File to wavsep server stdout to (default={})'.format(fn_out))
args = parser.parse_args()
install = ' '.join(argv[1:]).find('--mysql') >= 0
logging.debug("Install Server? {}".format(install))
if not install:
	previous = False
	if isfile(abspath(fn_flag)):
		with open(fn_flag) as flagfile:
			logging.debug('Loading parameters from {}'.format(fn_flag))
			previous = load(flagfile)
	logging.debug('Previous install detected? {}'.format(previous))
	if not previous:
		parser.error('Previous install not detected. Please provide at least one explicit --mysql-* argument.')
fn_out = args.out
fn_err = 'pico-wavsep_err.log'
server_out = open(fn_out, 'w')
server_err = open(fn_err, 'w')
try:
	server = start_server(args)
	if install:
	    install_db(server, parser, args, fn_flag)
	server.wait()
except KeyboardInterrupt as ki:
	logging.debug("Keyboard interrupt (likely CTRL-C.")
except CalledProcessError as cpe:
	logging.debug(
		"Exited Java process with exit code: {}".format(cpe.returncode))
finally:
	logging.info('Attempting to shut down server.')
	server.terminate()