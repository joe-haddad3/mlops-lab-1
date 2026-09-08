Question 1:Observe the files created, what do you think they contain:
uv init created pyproject.toml it contains everything related to the project like name version  author description , .python-version pins the Python version for the project , README.md  empty placeholder ,src/mlops_lab_1/__init__.py  the package source directory (src layout), containing a starter main() function.


Question 2:What are the created files. What do you think they are used for? And which ones should be pushed to git?
The files created are the .dvc folder is basically what turns a normal folder into a dvc repo, its just there to mark that. inside it .dvc/config is the project config file, right now its empty but later itll hold the dagshub remote info, and since its just config with no secrets it goes to git. .dvc/.gitignore is dvc auto creating a gitignore for its own stuff, telling git to skip config.local, tmp, and cache since those are local only (creds, temp state, actual cached data) so this file itself goes to git but what it lists doesnt. .dvc/tmp is just internal temp/lock files dvc uses while running, stays local. .dvc/cache is where the real data blobs get stored once you run dvc add, this is local too and its literally what dvc push sends up to the remote later. then at the root theres .dvcignore which works like gitignore but for dvc, telling it what to skip when scanning the folder, and that goes to git too.

what goes to git: .dvc/config, .dvc/.gitignore, .dvcignore, and later the .dvc pointer files plus whatever gitignore entries dvc adds. what stays out: cache, tmp, and especially config.local since thats where credentials would sit. this is the whole point of the lab, git handles code and pointers, dvc handles the actual data, both just live together in the same folder.


Question 3: Where are the credentials stored? and what are the options other than --global? Should the credentials be pushed to github?
when you run those dvc remote commands with --global, the credentials dont go anywhere inside your repo, they get stored in a global config file on your machine, usually under your user profile in something like ~/.config/dvc/config (on windows itll be in your appdata folder), completely separate from the project folder. as for options other than --global, you can use --local which stores it in .dvc/config.local inside the repo but that files gitignored by default so it never gets committed, or you can leave the flag off entirely which writes to the regular .dvc/config that IS shared and pushed to git, meaning thats the one option you should never use for actual credentials. and no, credentials should absolutely not be pushed to github, thats the whole reason --global or --local exist, so your password/token stays local to your machine while only the non-secret remote url and settings in .dvc/config go up to github for the team to share.


Question 4:Take a look at the .gitignore file. Explain what happened.
The uvc added /data to the .gitignore 


Question 5: Do you see a .dvc file? What does it contain?
Yes it contains cache\files\md5 and tmp a .gitignore and a config 

Question 6: You can check your main branch on the github web UI. Is the code there? Is the data there? Do you have any file that points to the data location. And what about dagshub web UI do you see the data?
In the github we have:
.dvc/  config folder
.dvcignore
.gitignore
data.dvc  the pointer file

No actual image files, no data/food11_raw/... folder visible anywhere. Exactly as expected: git only tracks the code and the small pointer, never the real data.

Question 7: In a completely new temporary folder clone your github repo. Do you see the data folder? What dvc command is needed to get the data folder?

.dvc/ — the config folder
.dvcignore
.gitignore
data.dvc — the pointer file

No data folder at all. This proves the point of the whole exercise: git only ever stored the small pointer file, never the actual image data. If you try to open data.dvc, you'll see the md5 hash, size, and file count, but the real content simply isn't here yet.

dvc pull is the command 

