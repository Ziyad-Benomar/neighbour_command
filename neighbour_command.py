#!/usr/bin/python


#########################################################################################
# THE CODE
#########################################################################################

from ansible.module_utils.basic import *
import telnetlib
import paramiko
import sys
import os
import time
import json



#----------------------------------------------------------------------------------------
# Utility functions
#----------------------------------------------------------------------------------------
def remove_empty(str_list) :
  while len(str_list) != 0 and str_list[0].replace(' ','') == '' :
    str_list.pop(0)
  while len(str_list) != 0 and str_list[-1].replace(' ','') == '' :
    str_list.pop()
  return str_list



def clean_lines(str_list) :
  # this function should remove ansi sequences (try the command 'write'  on cisco and look at output to understand :p)
  # I don't know how to remove them :(
  for i in range(len(str_list)) :
    if len(str_list[i])>200 :
      str_list[i] = "...[This line must be cleaned]..."
  return str_list



def contains(line, messages) : # line is a string, and messages is a string or list of strings
  if type(messages) == str :
    messages = [messages]
  for msg in messages :
    if msg in line :
      return True
  return False



def to_bool(item) :
  return str(item).lower() in ['y', 'yes', 'true']



def to_list(item) :
  if type(item) == list :
    return item
  return [item]



def str_time(seconds) :
  output = ''
  seconds = int(seconds*100)/100.0
  hours = int(seconds//3600)
  seconds = seconds%3600
  minutes = int(seconds//60)
  seconds = seconds %60
  if minutes != 0 :
    seconds = int(seconds)
  if hours!= 0 :
    output += str(hours) + ' hour(s) : '
  if minutes!=0 :
    output += str(minutes) + ' minute(s) : '
  output += str(seconds) + ' seconds'
  return output



def ping(host) :
  return ( int(os.system('ping -c 1 ' + host)) == 0 )



def get_error_output(message) :
  output = message[:]
  found = False
  while len(output) > 0 :
    line = output.pop(0)
    if "got output" in line :
      found = True
      break
  if not found :
    return message
  for i in range(len(output)) :
    output[i] = output[i][3:]
  return  output



def are_credentials(credentials) :
  if type(credentials) != list :
    return False
  for elt in credentials :
    if type(elt) != dict :
      return False
    elif not ('username' in elt and 'password' in elt) :
      return False
  return True



def cut_lost_connection_msg(response_output) :
  output = []
  response_output = get_error_output(response_output)
  for x in response_output :
    if x != connection_lost_msg :
      output.append(x)
    else :
      break
  return output



def concatenate_str_lists(str_or_list_1, str_or_list_2) :
  if type(str_or_list_1) == str :
    str_or_list_1 = [str_or_list_1]
  if type(str_or_list_2) == str :
    str_or_list_2 = [str_or_list_2]
  
  return str_or_list_1 +  str_or_list_2


def star_title(title, length) :
  title =  title + '    '
  return ['*'*length, title + '*'*(length-len(title)), '*'*100]

def connection_info_lines(connect_) :
  message = star_title('CONNECTION', 100)
  message += ['Established in  : '+ connect_['connection time']]
  message += ['Method          : '+ connect_['connection method']]
  message += ['Username        : '+ connect_['username']]
  message += ['Password        : '+ connect_['password']]
  message += [' '*100, ' '*100, ' '*100]
  return message

def commands_info_lines(commands_) :
  if len(commands_) == 0 :
    return []
  message = star_title('COMMANDS', 100)
  for command in commands_['output'] :
    message += ['-'*70, 'command        : ' +command['command'],'-'*70
    ] + command['output'] +[ ' '*70, ' '*70]
  return message


#----------------------------------------------------------------------------------------



#----------------------------------------------------------------------------------------
# Check that input has the correct format :
#----------------------------------------------------------------------------------------
def check_provider(provider) : #works
  failed = False
  message = []
  valid_attr = ['host', 'username', 'password', 'credentials', 'connection_method',
                'connection_timeout', 'port'
  ]
  for attribute in provider :
    if attribute not in valid_attr :
      failed = True
      message += ['- invalid option for provider : ' + str(attribute)]
  if failed :
    message += ['  valid options are ' + str(valid_attr)]
  if "host" not in provider or type(provider['host']) != str :
    message += ["- provider must contain key 'host', and it must be a string : its ip address"]
    failed = True
  if not (("username" in provider and "password" in provider) or "credentials" in provider) :
    message += ["- provider must contain keys 'username' and 'password', or 'credentials'"]
    failed = True
  elif 'username' in provider and (type(provider['username'])!=str or type(provider['password'])!=str) : 
    message += ["- 'username' and 'password' must be strings"]
    failed = True
  elif 'credentials' in provider and not are_credentials(provider['credentials']) :
      message += ["- 'credentials' must be a list of dictionaries with the keys 'username', 'password'"]
      failed = True

  if 'connection_method' in provider and provider['connection_method'] not in ['ssh', 'telnet'] :
    message += ["- 'connection_method' must be 'ssh' or 'telnet' or not given at all",
                "  if 'connection_method' is not given, both methods will be tested"
    ]
    failed = True
  #Set default connection_timeout value
  if 'connection_timeout' not in provider :
    provider['connection_timeout'] = 5
  provider['connection_timeout'] = int(provider['connection_timeout'])
  if failed :
    message = ['*'*50,' '*11+"ERROR(S) FOUND IN 'provider'"+' '*11, '*'*50] + message + ['*'*50, '']

  return {'failed': failed, 'message': message} #done is bool, message is list



def check_commands(commands) : #works
  failed = False
  message = []
  error_message = [
    "- each command must be String or dictionary having at least the key 'run'"
  ]
  valid_attr = ['run', 'expect', 'answer', 'loop', 'will_reboot']
  
  for command in commands :
    msg = []
    
    if not (type(command) == str or (type(command) == dict and 'run' in command) ) :
      msg += ["- each command must be a string or a dictionnary having at least the key'run'"]
    elif type(command) == dict :
      invalid_attr = False
      for attribute in command :
        if attribute not in valid_attr :
          invalid_attr = True
          msg += ['- invalid option for command : ' + str(attribute)]
      if  invalid_attr :
        msg += ['  valid options are ' + str(valid_attr)]
      if 'expect' in command and 'answer' in command and len(to_list(command['expect'])) == len(to_list(command['answer'])):
        pass
      elif not ('expect' in command or 'answer' in command) :
        if 'loop' in command :
          msg += ["- 'loop' can only be used with 'expect' and 'answer'"]
      else :
        msg += ["- each command must either contain keys 'expect' and 'answer' or not contain any of them",
                "  when it contains them, they must have the same length : an answer for each expected message" ]
    if len(msg) > 0 :
      failed = True
      if type(command) == dict and 'run' in command :
        command_ = command['run']
      else :
        command_ = command
      message += ["error found in the command : " + str(command_) ] + msg + ['']
  
  if failed :
    message = ['*'*50,' '*11+"ERROR(S) FOUND IN 'commands'"+' '*11,'*'*50] + message[:-1] + ['*'*50, '']
  
  return {'failed': failed, 'message': message} #done is bool, message is list



def check_input(provider, commands) : #works
  message = []
  failed = False
  check_provider_ = check_provider(provider)
  check_commands_ = check_commands(commands)
  message = check_provider_['message'] + check_commands_['message']
  failed  = check_provider_['failed'] or check_commands_['failed']
  return {'failed':failed, 'message':message} #done is bool, message is list
#----------------------------------------------------------------------------------------



#----------------------------------------------------------------------------------------
# SSH connection :
#----------------------------------------------------------------------------------------
def connect_ssh() : #works
  global remote, username, password, prompt_message, prompt_symbol
  username = ''
  password = ''

  done = False
  message = ['Failed to connect : the device is unreachable or none of the given credentials is correct',
             "default connection port for 'ssh' is 22, it can be changed if another port should be used instead",
             'default connection_timeout is 5 seconds, it can be changed if more time is needed to connect to the device'
  ]

  if 'credentials' in provider :
    credentials = provider['credentials']
  else :
    credentials = [{'username':provider['username'], 'password':provider['password']}]
  host = provider['host']

  if 'port' in provider and 'connection method' in provider :
    connection_port = provider['port']
  else :
    connection_port = 22
  connection_timeout = provider['connection_timeout']

  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

  for c in credentials :
    try :
      ssh.connect(host, username = c['username'], password = c['password'], port = connection_port, timeout = connection_timeout)
    except :
      continue
    done = True
    message = ['connected']
    username = c['username']
    password = c['password']
    break
      
  if done :
    remote = ssh.invoke_shell()
    time.sleep(0.1)
    prompt_message = ''
    while remote.recv_ready() :
      prompt_message += remote.recv(1024).decode('ascii')
    prompt_message = prompt_message.splitlines()[-1]
    prompt_symbol  = prompt_message[-1]
    prompt_message = prompt_message[:-1]

  return {'failed': not done, 'output': message} #done is bool, message is list
#----------------------------------------------------------------------------------------



#----------------------------------------------------------------------------------------
# TELNET connection :
#----------------------------------------------------------------------------------------
def connect_telnet() : #works
  global remote, username, password, prompt_message, prompt_symbol
  username = ''
  password = ''

  done = False
  message = ['Failed to connect : the device is unreachable or none of the given credentials is correct',
             "default connection port for 'telnet' is 23, it can be changed if another port should be used instead",
             'default connection_timeout is 5 seconds, it can be changed if more time is needed to connect to the device'
  ]

  user_msg = ['username', 'user name', 'user', 'Username', 'UserName', 'User Name', 'User', 'USERNAME', 'USER NAME', 'USER']
  password_msg = ['password', 'pass word', 'Password', 'PassWord', 'Pass Word', 'PASS WORD' 'PASSWORD']
  fail_msg = ['failed', 'Failed', 'FAILED', 'fail', 'Fail', 'FAIL']
  fails = user_msg + password_msg + fail_msg

  if 'credentials' in provider :
    credentials = provider['credentials']
  else :
    credentials = [{'username':provider['username'], 'password':provider['password']}]
  host = provider['host']
  if 'port' in provider and 'connection method' in provider :
    connection_port = provider['port']
  else :
    connection_port = 23
  connection_timeout = provider['connection_timeout']
  
  for c in credentials :
    try:
      remote = telnetlib.Telnet(host, port=connection_port, timeout=connection_timeout)
    except:
      continue
    remote.expect([msg.encode('ascii') for msg in user_msg ], 10)
    remote.write(c['username'].encode('ascii') + b"\n")
    remote.expect([msg.encode('ascii') for msg in password_msg ], 10)
    remote.write(c['password'].encode('ascii') + b"\n")
    time.sleep(1)
    output = remote.read_very_eager().decode('ascii')
    identified = True
    for w in fails :
      if w in output :
        remote.close()
        identified = False
    if identified :
      prompt_message = output.splitlines()[-1]
      prompt_symbol  = prompt_message[-1]
      prompt_message = prompt_message[:-1]
      username = c['username']
      password = c['password']
      done = True
      message = ['connected']
      break

  return {'failed': not done, 'output': message} #done is bool, message is list
#----------------------------------------------------------------------------------------



#----------------------------------------------------------------------------------------
# Reboot
#----------------------------------------------------------------------------------------
def wait_for_closed_connection(host, timeout = 60) :
  start_time = time.time()
  is_available = ping(host)
  failed = False
  error_message = [
    "timeout error : "+host+" didn't shut down after the limit time",
    "the default reboot_timeout is 300 seconds, it can be changed if more time is needed to reboot the device"
  ]
  while is_available :
    if time.time() - start_time > timeout :
      failed = True
      break
    is_available = ping(host)
  return {'failed': failed, 'message': error_message}



def wait_for_active_connection(host, timeout = 60) :
  start_time = time.time()
  is_available = ping(host)
  failed = False
  error_message = [
    "timeout error : "+host+" is still unreachable after the limit waiting time",
    "the default reboot_timeout is 300 seconds, it can be changed if more time is needed to reboot the device"
  ]
  while not is_available :
    if time.time() - start_time > timeout :
      failed = True
      break
    is_available = ping(host)
  return {'failed': failed, 'message': error_message}



def wait_for_reboot(host, timeout = 300) :
  start_time = time.time()
  shut_down = wait_for_closed_connection(host, timeout)
  if shut_down['failed'] :
    return shut_down
    #return {'failed': True, 'message': shut_down['message']}
  
  remaining_time = timeout - (time.time() - start_time)
  turn_on = wait_for_active_connection(host, remaining_time)
  if turn_on['failed']  :
    return turn_on
  
  reboot_time = time.time() - start_time

  message = ["*"*50,' '*15 + "succesfuly rebooted " + ' '*15, "*"*50]
  failed = False

  connect_ = connect_set_functions()
  if connect_['failed'] :
    failed = True
    message += connect_['output']

  return {'failed': failed, 'message': message, 'reboot time': reboot_time }
#----------------------------------------------------------------------------------------


#----------------------------------------------------------------------------------------
# Elementary functions
#----------------------------------------------------------------------------------------
# FOR SSH CONNECTION
#--------------------
def read_available_ssh() :
  time.sleep(0.1)
  output = ''
  while remote.recv_ready() :
    output += remote.recv(1024).decode('ascii')
  return output



def write_ssh(answer) :
  remote.send(answer)



# FOR TELNET CONNECTION
#-----------------------
def read_available_telnet() :
  time.sleep(0.1)
  output = ''
  return remote.read_very_eager().decode('ascii')



def write_telnet(answer) :
  remote.write(answer.encode('ascii'))
#----------------------------------------------------------------------------------------



#----------------------------------------------------------------------------------------
# Set the functions we'll use depending on the connection method
#----------------------------------------------------------------------------------------
def set_functions() :
  global connect, read_available, write

  if provider['connection_method'].lower() == 'ssh' :
    connect = connect_ssh
    read_available = read_available_ssh
    write = write_ssh

  if provider['connection_method'].lower() == 'telnet' :
    connect = connect_telnet
    read_available = read_available_telnet
    write = write_telnet



def test_connection() :
  connect_telnet_ = connect_telnet()
  if not connect_telnet_['failed'] :
    provider['connection_method'] = 'telnet'
    return connect_telnet_

  connect_ssh_ = connect_ssh()
  if not connect_ssh_['failed'] :
    provider['connection_method'] = 'ssh'
    return connect_ssh_
  
  message = ['*'*50, ' '*8+'ERROR :  Failed to connect to host'+' '*8, '*'*50,
             'Failed to connect : the host is unreachable or none of the given credentials is correct',
             "default connection port for 'telnet' is 23, and for 'ssh' is 22. it can be changed if another port should be used instead",
             'default connection_timeout is 5 seconds, it can be changed if more time is needed to connect to the device'
  ]
  return {'failed': True, 'output': message}



def connect_set_functions() :
  start_time = time.time()
  if 'connection_method' not in provider :
    test_connection_ = test_connection()
    if test_connection_['failed'] :
      return test_connection_
    set_functions()
  else :
    set_functions()
    test_connection_ = connect()
  test_connection_['connection time'] = str_time(time.time() - start_time)
  return test_connection_
#----------------------------------------------------------------------------------------


#----------------------------------------------------------------------------------------
# Functions to run commands (for both SSH and TELNET)
#----------------------------------------------------------------------------------------
def update_prompt(prompt) :
  global prompt_message, prompt_symbol
  if prompt == '' :
    return False
  new_prompt_msg    = prompt[:-1]
  new_prompt_symbol = prompt[-1]
  if new_prompt_msg == prompt_message or new_prompt_symbol == prompt_symbol :
    prompt_message = new_prompt_msg
    prompt_symbol  = new_prompt_symbol
    return True



def ping_read_available() :
  if ping(provider['host']) :
    return read_available()
  else :
    return '\n' + connection_lost_msg



def write_command(command, expected = '#') :
  write(command.encode('ascii'))
  start_time = time.time()
  received = ''
  # We had to use this loop in case there are long commands
  while command not in received :
    received += read_available()
    if time.time() - start_time > 5 :
      break
    if len(command) > 50 and command[-50:] in received :
      break 
  write('\n')



def read_expect( expected = "#", timeout = 60) :
  start_time = time.time()
  failed = False
  output = ''
  output_last_line = 'empty'
  while True :
    partial_output = ping_read_available()
    output += partial_output
    if connection_lost_msg in partial_output :
      output_last_line = connection_lost_msg
      failed = True
      break
    if partial_output=='' and len(output)>0 and contains(output.splitlines()[-1], expected) :
      break
    if time.time() - start_time > timeout :
      failed = True
      break
  output = output.splitlines()
  output_last_line = output.pop()

  #The following check is to handle the very rare case where the expected message is read exactly at
  #end of allowed time (happended once when testing :p)
  if contains(output_last_line, expected) :
    failed = False

  return {'failed': failed, 'output': output, 'output_last_line': output_last_line }



# run an str command and wait for it to end (or timeout)
# expected_msg can be a list or a string
def run_str_command(command, expected_msg = '#', timeout = 60) : #works
  write_command(command)
  response = read_expect(expected_msg, timeout)
  
  failed = response['failed']
  output = clean_lines(response['output'])
  output_last_line = [ response['output_last_line'] ]

  output = remove_empty(output)
  if failed :
    got_output = ["   " + line  for line in output + output_last_line]
    output = [
      "timeout error : didn't get the expected output at the end of dedicated time",
      "default connection_timeout is 60 seconds, it can be changed if more time is needed to run the command",
      "expected output : " + str(expected_msg),
      "got output : " 
    ] + got_output
  
  return {'command': command, 'failed': failed, 'output': output, 'output_last_line': response['output_last_line']} 



def run_dict_command_loop(command, expected_msg = "#", timeout = 60) :
  start_time = time.time()
  expect = concatenate_str_lists(command['expect'][0], expected_msg)
  answer = command['answer'][0]

  response = run_str_command(command['run'], expect, timeout)
  output_last_line = response['output_last_line']

  if response['failed'] :
    return response
  
  del response['output_last_line']
  
  continue_loop = True
  if contains(output_last_line, expected_msg) :
    continue_loop = False

  failed = False
  output = remove_empty(response['output'])
  output_last_line = ''

  while continue_loop :
    write(answer)
    remaining_time = timeout - (time.time() - start_time)
    returned = read_expect(expect, remaining_time)

    output += remove_empty(returned['output'])
    output_last_line = [returned['output_last_line']]

    if returned['failed'] :
      failed = True
      got_output = ["   " + line  for line in output + output_last_line]
      output = [
        "timeout error : didn't get the expected output at the end of dedicated time",
        "default connection_timeout is 60 seconds, it can be changed if more time is needed to run the command",
        "expected output : " + str(expect),
        "got output : "
      ] + got_output
      break
    if contains(output_last_line[0], expected_msg) :
      break

  output = clean_lines(output)
  return {'command': command['run'], 'failed': failed, 'output': output, 'output_last_line': output_last_line} 



#run a dict command (run, expect, answer) and wait for it to complete or timeout
def run_dict_command_no_loop(command, expected_msg = "#", timeout = 60) : #works
  start_time = time.time()
  expect = command['expect']
  answer = command['answer']
  expect.append(expected_msg)

  response = run_str_command(command['run'], command['expect'][0], timeout)
  if response['failed'] :
    return response
  
  failed = False
  output = remove_empty(response['output'])
  output_last_line = ''
  
  for i in range(len(answer)) :
    write(answer[i])
    remaining_time = timeout - (time.time() - start_time)
    returned = read_expect(expect[i+1], remaining_time)
    
    output += remove_empty(returned['output'])
    output_last_line = [returned['output_last_line']]

    if returned['failed'] :
      failed = True
      got_output = ["   " + line  for line in output + output_last_line]
      output = [
        "timeout error : didn't get the expected output at the end of dedicated time",
        "default connection_timeout is 60 seconds, it can be changed if more time is needed to run the command",
        "expected output : " + str(expect[i+1]),
        "got output : "
      ] + got_output
      break

  output = clean_lines(output)
  return {'command': command['run'], 'failed': failed, 'output': output, 'output_last_line': output_last_line} 



def run_dict_command(command, expected_msg = "#", timeout = 60) :
  if type(command['expect']) == str :
    command['expect'] = [command['expect']]
  if type(command['answer']) == str :
    command['answer'] = [command['answer']]
  if 'loop' in command and to_bool(command['loop']) ==  True :
    return run_dict_command_loop(command, expected_msg, timeout)
  else :
    return run_dict_command_no_loop(command, expected_msg, timeout)



# run all the commands
def run_commands(commands, command_timeout=60, reboot_timeout=300) : #works
  failed = False
  output = []
  expected_msg = [prompt_message, prompt_symbol]

  for command in commands :

    start_time = time.time()
    
    will_reboot = ('will_reboot' in command and to_bool(command['will_reboot']))

    if type(command) == dict and 'expect' not in command:
      command = command['run']
      
    if type(command) == str : 
      response = run_str_command(command, expected_msg, command_timeout)

    else : # type(command)==dict
      response = run_dict_command(command, expected_msg, command_timeout)

    if will_reboot :
      waiting_msg = ['','*'*50, ' '*14 + 'waiting for reboot ...' +' '*14,'*'*50, '']
      response['output'] = cut_lost_connection_msg(response['output']) + waiting_msg
      reboot = wait_for_reboot(provider['host'], reboot_timeout)
      response['failed'] = reboot['failed']
      response['output'] += reboot['message']
    elif (len(response['output']) > 0 and connection_lost_msg in response['output'][-1]) :
      failed_connection_msg = ['','*'*50, ' '*12+'ERROR : Connection is lost' +' '*12,'*'*50, '',
                           "If the device is expected to reboot, the option 'will_reboot' must be added to this command and set to 'yes'."
      ]
      response['output'] = cut_lost_connection_msg(response['output']) + failed_connection_msg
      

    if response['failed'] :
      failed = True
    
    execution_time = time.time() - start_time
    
    if not failed and read_available() == '' :
      update_prompt(response['output_last_line'])

    del response['output_last_line']
    response['execution time'] =  str_time(execution_time)
    output.append(response)

    if failed :
      break

  return {'failed': failed, 'output': output}
#----------------------------------------------------------------------------------------



#----------------------------------------------------------------------------------------
# Main  :
#----------------------------------------------------------------------------------------
def main():
  #global get_firmware, firmware_table, needed_firmware
  global connection_lost_msg, provider, command_timeout

  connection_lost_msg = "$$$**_-_-**||\__CONNECTION IS LOST__/||**-_-_**$$$"

  #READING INPUT --------------------------------------------
  fields = {
     "provider": {"required": True, "type": "dict"},
     "commands": {"required": False, "default": [], "type": "list"},
     "command_timeout": {"required": False, "default": 60, "type": "float"},
     "reboot_timeout": {"required": False, "default": 300, "type": "float"}
  }
  module = AnsibleModule(argument_spec=fields)
  provider = module.params["provider"]
  commands = module.params["commands"]
  command_timeout = module.params['command_timeout']
  reboot_timeout = module.params['reboot_timeout']
  
  #CHECKING INPUT FORMAT -------------------------------------
  check_input_ = check_input(provider, commands)
  if check_input_['failed'] :
    module.exit_json(
      changed=False,
      failed=True,
      stdout='',
      stderr=str(check_input_['message'])
    )


  #CONNECT --------------------------------------------------
  connect_ = connect_set_functions()
  if connect_['failed'] :
    module.exit_json(
      changed=False,
      failed=True,
      stdout='',
      stderr=str(connect_['output'])
    )
  connect_['password'] = password
  connect_['username'] = username
  connect_['connection method'] = provider['connection_method']
  connect_['connection established in'] = connect_['connection time']
  #del  connect_['connection time']
  del connect_['output']
  
  response = connection_info_lines(connect_)

  #RUN COMMANDS ---------------------------------------------
  run_commands_ = run_commands(commands, command_timeout, reboot_timeout)
  run_commands_['number of succesfuly executed commands'] = len(run_commands_['output'])
  if run_commands_['failed'] :
    run_commands_['number of succesfuly executed commands'] -= 1
    run_commands_['output'] = run_commands_['output']
    response += commands_info_lines(run_commands_) + ["FAILED : The command nb "+str(len(run_commands_['output']))+" has failed"]
    module.exit_json(
      changed=False,
      failed=True,
      stdout='',
      stderr=str(response)
    )
  if len(commands) > 0 :
    response += commands_info_lines(run_commands_)


  #END -----------------------------------------------------
  
  module.exit_json(
    changed=False,
    failed=False,
    stdout=str(response),
    stderr=''
  )

if __name__ == '__main__':
  main()
