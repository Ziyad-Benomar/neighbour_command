# neighbour_command
An ansible module written with python, that allows to run commands on a neighbour remote machine, reachable via ssh or telnet  
short_description: Sends commands from a server to switchs that are connected to it.  

The host for this module must be a Unix like system (MacOS, Linux) having Python installed.  
It also must have the libraries Paramiko and Telnet installed.  

Unfortunatly I didn't have enough time to write a proper documentation, but the file "test.yml" and the following description should give you a good example of the main use cases of this module.  

As for all Ansible modules, to use 'neighbour_command' in an Ansible script, you should create a folder 'library' in the same directory as your script, and the file 'neighbour_command.py' in it.  
For example, to run 'complete_test.yml', you should have the following folder's topology :

/-----------------------------------------------          
MainFolder/                         
| --> library/                        
|     | --> neighbour_command.py       
| --> complete_test.yml                  
\-----------------------------------------------     

## Detailed description
During my summer internship at Wifirst, I had to write Ansible playbooks to automate tasks on different equipment (switches, computers, servers).  

However, I had to manipulate switches with different connection identifiers and also different connection protocols (SSH, Telnet).  

Hence my motivation to write this module, which takes as Host a main machine, and as input the neighboring machine you want to manipulate. It uses the Paramiko and Telnetlib python libraries to test both SSH and Telnet connection protocols respectively, and it also tests several user/password pairs.  

Then it takes the list of commands you want to run on the neighboring machine:   
The 'commands' list gathers all these commands.  
A command can be :  

- a String: the command is executed and we have directly its output.  

- a dictionary with the attributes: 'run', which contains the command; 'expect' which indicates the response to the expected prompt; and 'answer' which indicates the message with which we are going to respond.   

- Expect' and 'answer' can be strings, or even lists, in case we expect a series of messages and want to give a series of answers.   

- a dictionary with the attributes 'run', 'expect', 'answer', which are strings this time, and also 'loop', which is a boolean attribute, and which indicates if we should expect to receive the message 'expect' in a loop an undetermined number of times. For example, if we don't know how many times we'll get a message like "are you sure you want to continue? [Y/N]", but you are sure you want to answer "Y" each time.    

- If a command will reboot the neighboring machine, it is necessary to add the 'will_reboot' attribute and give it the value 'yes', in order to prevent the program that the connection will be lost and that it will have to wait for it to be restored, and not end with an error.   


I tested and used this module for many purposes and in many cases, and it worked fine.  
But maybe there are still some exceptions that I didn't pay attention to. So please feel free to contact me and report any bugs.

