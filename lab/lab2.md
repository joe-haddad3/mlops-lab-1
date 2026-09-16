Question 1: Look at pyproject.toml and uv.lock. What changed?

pyproject.toml gained mlflow, pillow, scikit-learn, torch and torchvision in dependencies. It also gained a [[tool.uv.index]] block for PyTorch's cu132 index and a [tool.uv.sources] block, since my RTX 5050 is Blackwell (sm_120) and needs CUDA 13.2 wheels that aren't on regular PyPI, torchvision pulls from the cu132 index while torch comes from a local wheel file since that's how I ended up getting it. requires-python also got narrowed to ==3.11.* to match that wheel's build.

uv.lock got regenerated to record the exact resolved versions, torch 2.14.0+cu132 and torchvision 0.29.0+cu132 in my case, plus hashes and where each package came from, cu132 index, local wheel, or plain PyPI depending on the package.


Question 2: What is `--backend-store-uri` used for? What is `--default-artifact-root` used for? What is the difference between the metadata mlflow stores and the artifacts it stores?

backend store uri is basically telling mlflow where to keep all the tracking info, like the experiments, the runs, the params and metrics, that's all structured data so it goes into a database, in your case a sqlite file called mlflow.db.

default artifact root is different, that's where the actual files from a run get saved, so stuff like the trained model itself, plots, checkpoints, anything that's a real file and not just a number or a string.

the difference between the two is metadata vs artifacts. metadata is small structured stuff that mlflow uses to build the tables and charts you see in the ui. artifacts are the bigger actual files, they just get stored separately and the metadata keeps a link pointing to where they are.


Question 3: Why shouldn't `mlflow.db` and `mlruns/` be tracked by git, and why shouldn't they be tracked by dvc either?

mlflow.db and mlruns are just local outputs that get created every time you run training on your machine, they're not something you write by hand and they change constantly. Putting them in git would be messy since it's basically a database file getting overwritten over and over, that causes conflicts and just bloats the repo for no reason. Same logic for dvc, dvc is meant for tracking actual data you care about the history of, like your datasets or a final model you're shipping, not some local tracking server cache that's regenerated every run.

 Question 4: What happens the first time you call `set_experiment` with a name that doesn't exist yet? Check the mlflow UI.

 
the first time you call set_experiment with a name that doesn't exist yet, mlflow just creates it automatically, it makes a new experiment with that name and a fresh id and sets it as the active one for whatever runs come after. you can literally watch it happen in the ui, before you run anything the food11 experiment doesn't exist, then the second your script calls set_experiment it shows up in the sidebar with zero runs, then runs start appearing as your script logs them.


Question 5: What is the difference between `mlflow.log_param` and `mlflow.log_metric`? Why does `log_metric` take a `step` argument and `log_param` doesn't?

log_param is for stuff that's fixed before training even starts and doesn't change while it's running, like learning rate or batch size, you set it once and that's it. log_metric is for stuff that comes out of training and changes over time, like loss or accuracy, since those get calculated every epoch as the model trains. that's exactly why log_metric takes a step argument and log_param doesn't, step lets mlflow know which point in training that value belongs to, so it can plot a line chart of how the metric changed over epochs. a param doesn't have a "point in time" since it's just one fixed value for the whole run, so there's nothing to plot against.


Question 6: Open the run in the mlflow UI. Find the params, the metric charts, and the logged model artifact. Where does the model artifact actually live on disk?

if you open the run in the ui you'll see three tabs basically, one shows the params like dataset, epochs, lr, batch_size exactly as they were logged. another shows the metrics as line charts, so train_loss, val_loss, and val_accuracy each get their own chart going up or down across the epochs. then there's the artifacts tab where the logged model shows up under a folder called "model". as for where it actually lives on disk, it's inside the mlruns folder, under a path like mlruns/<experiment_id>/<run_id>/artifacts/model, since that's the default artifact root we set when starting the server.


Question 7: In the mlflow UI, open the `food11` experiment. Select these runs and click "Compare". Which learning rate gave the best `val_accuracy`? Is higher always better?


lr=0.0001 gave the best val_accuracy by far, gentle-koi-947 hit 0.78 val_accuracy and 0.82 test accuracy, way ahead of everything else. lr=0.01 basically destroyed the model, val_accuracy stayed around 0.10 to 0.13 the whole time, which is close to random guessing since there's 11 classes (1/11 is about 0.09). so no, higher is definitely not always better, too high a learning rate makes the model take steps so big it can't actually converge, it just bounces around instead of learning anything useful.



 Question 8: Use the parallel coordinates plot on the compare page to look at `lr`, `batch_size` and `val_accuracy` together. What pattern do you see?

on the parallel coordinates plot the clearest pattern is that lr dominates everything else, the line for lr=0.01 drops straight down to terrible val_accuracy no matter what batch size it's paired with, while lr=0.0001 lines end up at the top with the best val_accuracy. batch_size seems to matter a lot less than lr in this range, going from 32 to 64 at lr=0.001 actually helped a bit (0.53 vs 0.59), but it's a small effect compared to how much lr swings the results.

Question 9: Sort the runs table by `val_accuracy` descending. Which run is the best one? Note its run ID, you'll need it in the next lab.



after sorting the runs table by val_accuracy descending, gentle-koi-947 comes out as the best run, with val_accuracy 0.7801 and test_accuracy 0.8248, using lr=0.0001 and batch_size=32.un ID is 1e2a05b011e54ed180f42138135a6516, noting that down since it's needed for the next lab.