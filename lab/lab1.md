Question 1:Observe the files created, what do you think they contain?

uv init created pyproject.toml it contains everything related to the project like name version  author description , .python-version pins the Python version for the project , README.md  empty placeholder ,src/mlops_lab_1/__init__.py  the package source directory, containing a starter main() function.


Question 2:What are the created files. What do you think they are used for? And which ones should be pushed to git?

The files created are the .dvc folder is basically what turns a normal folder into a dvc repo, its just there to mark that. inside it .dvc/config is the project config file, right now its empty but later itll hold the dagshub remote info, and since its just config with no secrets it goes to git. .dvc/.gitignore is dvc auto creating a gitignore for its own stuff, telling git to skip config.local, tmp, and cache since those are local only (creds, temp state, actual cached data) so this file itself goes to git but what it lists doesnt. .dvc/tmp is just internal temp/lock files dvc uses while running, stays local. .dvc/cache is where the real data blobs get stored once you run dvc add, this is local too and its literally what dvc push sends up to the remote later. then at the root theres .dvcignore which works like gitignore but for dvc, telling it what to skip when scanning the folder, and that goes to git too.

what goes to git: .dvc/config, .dvc/.gitignore, .dvcignore, and later the .dvc pointer files plus whatever gitignore entries dvc adds. what stays out: cache, tmp, and especially config.local since thats where credentials would sit. this is the whole point of the lab, git handles code and pointers, dvc handles the actual data, both just live together in the same folder.


Question 3: Where are the credentials stored? and what are the options other than --global? Should the credentials be pushed to github?

when you run those dvc remote commands with --global, the credentials dont go anywhere inside your repo, they get stored in a global config file on your machine, usually under your user profile in something like ~/.config/dvc/config (on windows itll be in your appdata folder), completely separate from the project folder. as for options other than --global, you can use --local which stores it in .dvc/config.local inside the repo but that files gitignored by default so it never gets committed, or you can leave the flag off entirely which writes to the regular .dvc/config that IS shared and pushed to git, meaning thats the one option you should never use for actual credentials. and no, credentials should absolutely not be pushed to github, thats the whole reason --global or --local exist, so your password/token stays local to your machine while only the non-secret remote url and settings in .dvc/config go up to github for the team to share.


Question 4:Take a look at the .gitignore file. Explain what happened.

The dvc added /data to the .gitignore 


Question 5: Do you see a .dvc file? What does it contain?

yes, dvc add data created data.dvc at the root. its a small yaml pointer file that contains the path it tracks (data), the md5 hash of the whole folder ending in .dir which means its a hash of a listing of every file not just one file, the total size in bytes and the number of files, plus the hash algorithm used. thats all git stores, the tiny pointer, while the real 1.27gb sits in the dvc cache and on dagshub.

Question 6: You can check your main branch on the github web UI. Is the code there? Is the data there? Do you have any file that points to the data location. And what about dagshub web UI do you see the data?

on github the code is all there, i can see src/food11/data.py, src/mlops_lab_1/init.py, pyproject.toml, uv.lock, .python-version, README.md and my lab/lab1.md, plus the dvc stuff which is .dvc/config, .dvcignore and .gitignore. the data itself is not there at all, no data folder, no images, nothing, because /data is gitignored. but i do have the file that points to the data which is data.dvc, it holds the md5 hash, the total size and the number of files, so git knows exactly which version of the data belongs to this commit even though it doesnt store the data. and on dagshub its the opposite, if i open the repo there and go to the data tab i can see the actual data folder with food11_raw, food11_processed and food11_processed_mini and the real images inside. so github has the code and the pointer, dagshub has the real data, which is exactly the split this whole lab is about.

Question 7: In a completely new temporary folder clone your github repo. Do you see the data folder? What dvc command is needed to get the data folder?

.dvc/ — the config folder
.dvcignore
.gitignore
data.dvc — the pointer file

No data folder at all. This proves the point of the whole exercise: git only ever stored the small pointer file, never the actual image data. If you try to open data.dvc, you'll see the md5 hash, size, and file count, but the real content simply isn't here yet.

dvc pull is the command 

Question 8: Do you still see the new folders you created? food11_processed and food11_processed_mini?

i ran git log --oneline -- data.dvc to see the commits that touched the pointer, then git checkout 2e84c25 which is the commit right before i added the processed data, then dvc checkout. no, food11_processed and food11_processed_mini are not there anymore, only food11_raw shows up in the data folder. what happened is git checkout swapped data.dvc back to the older pointer with the old hash and the smaller file count, then dvc checkout read that pointer and rebuilt the data folder to match it, so it deleted the two processed folders since they didnt exist at that commit. nothing is actually lost though, everything is still sitting in .dvc/cache, so git checkout main followed by dvc checkout brings them straight back. this is the part that shows how git and dvc work together, git versions the pointer and dvc uses that pointer to swap the real data to the matching version.