# Recipe Catalog App
This app allows users to create different food groups (from different nationalities, that is). Within each food group, users can create new recipes at different difficulty levels. This app is intended for users who are hungry but aren't sure what for. They can go to this app, choose a food group that sounds appealing, and choose the suitable difficulty level. 

## Important note
Many of the steps taken to run this app are done from the command line (bash in my case). Some basic comfortability using CLI's is recommended for this project. 

### Getting started
1. Clone or download this repo onto your computer

2. Install VirtualBox. Download it from 'virtualbox.org'

3. Install Vagrant. Download it from 'vagrantup.com'

4. Configure the Vagrant virtual machine. The zip file to configure the virtual machine is included. Its called 'fsnd-virtual-machine.zip'. Decompress this file and save it wherever you like.

5. Power on the virtual machine. Change directory (using the `cd directory_name` command in your command line) into the directory which contains the virtual machine folder which you just decompressed, and then change directory again into the `vagrant` directory from there. Run the command `vagrant up` to power on the virtual machine. 

6. Log into the virtual machine. Run the command `vagrant ssh` to log in. 

7. Navigate to the folder where all the files for this project are stored. This can be done by running `cd /vagrant/catalog_project` in the command line.

8. Initialize the Postgres database. Run the command `python database_setup.py`. This will set up all of the tables necessary for this app to run.

9. Start the server! Run the command `python main.py` to start the server. You will not be able to use the command line for anything else while the server is running (you'd have to open another command line to do anything else). 

10. Visit the website! The server is being hosted on port 2000. So the address is 'http://localhost:2000'

11. Stop the server. Run the command `CTRL-C` to stop the server. This will bring you back to your normal command line. 

12. Exiting the virtual machine. You can exit the virtual machine by typing `exit` or `CTRL-D` into the command line, as long as you're not running any other program from the command line. 
