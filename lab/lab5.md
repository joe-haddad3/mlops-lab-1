# Lab 5 answers

notes on what i changed vs the lab text:

- serve.py uses fastapi's `lifespan` instead of `@app.on_event("startup")`. on_event is deprecated in the fastapi version i have, lifespan does the same thing (runs once when the app starts, and TestClient triggers it when used as a context manager). same idea as the lab: `model` is a module level variable, loading is skipped when `SKIP_MODEL` is set, `/predict` returns 503 if `model is None`. `/health` also reports `model_loaded` now.
- added `[tool.pytest.ini_options] pythonpath = ["."]` so `from src.food11...` imports work in pytest.
- added `known-third-party = ["mlflow"]` for ruff's import sorting. the repo has a `mlflow/` folder (the dockerfile for the mlflow server from lab 4), so ruff thought `import mlflow` was a first party import and wanted it in its own block.
- the ruff version i got (0.17) enables more rules by default than the old E/F set, it flagged a few things in train.py too (`import torch.nn as nn`, unused `test_loss`). i fixed them instead of turning the rules off.
- added a third api test, `/predict` returns 503 when there is no model.

---

Question 1: Why is it a bad idea for a unit test to load the real model from your MLflow server? List at least two ways the test could fail even though your code is correct.

because then the test isn't testing my code anymore, it's testing my whole infrastructure, and it fails for reasons that have nothing to do with the line i just changed.

ways it fails with correct code:

- the server isn't reachable. on a github runner there is no mlflow at all, my server is a container on my laptop. it's exactly the lab 4 question 6 crash, `NameResolutionError` / connection refused, before a single assertion runs. same on my laptop if i forget `docker compose up`.
- the registry state is different. after `docker compose down -v` there is no food11 model and the alias lookup gives `RESOURCE_DOES_NOT_EXIST`. or someone moved `champion` to another version, like my broken v2 from lab 4, and now the "Bread" assertion fails because the *model* changed, not the code.
- it's slow and heavy. downloading 52mb of weights and running a resnet on every test run turns a 1 second suite into a minute, so people stop running it.
- the model's answer is not mine to assert on. a real model can say Dessert for my bread image, that's a model quality question, not a "does my api build valid json" question.

before this lab it was even worse, serve.py called load_model at import time, so just `import src.food11.serve` in a test file would already try to reach mlflow.

---

Question 2: The fake model always answers "Bread" with 0.90 confidence. What exactly does `test_predict_returns_valid_json` prove, and what does it *not* prove?

it proves my code around the model works: the multipart upload is accepted, the jpeg bytes are decoded, the image goes through the transform into a `(1, 3, 224, 224)` float32 batch without crashing, whatever the model returns is turned into probabilities, the argmax index is mapped to the right class name, and the response is json with `category` and a `confidence` between 0 and 1.

one detail, it doesn't actually come back with 0.90. my serve.py treats the model output as logits and applies softmax, so `[0.90, 0.01 x10]` becomes `e^0.9 / (e^0.9 + 10 e^0.01)`, about 0.196 for Bread. the test still passes because it only checks the class and that the confidence is in [0, 1]. if i'd written `confidence == 0.9` it would have caught that the fake doesn't match what serve.py expects from a real model.

what it does not prove:

- that the real model is any good, or even that it predicts Bread for this image
- that the real model's input format matches what i send (shape, dtype, normalisation). the fake accepts anything
- that the real model's output format matches what i parse. if the pyfunc started returning a dataframe or already softmaxed probabilities, the fake wouldn't notice
- that loading from mlflow works, `models:/food11@champion` resolves, the alias exists
- anything about performance, memory, concurrency

---

Question 3: Which check caught it? Why is a train/test duplicate more dangerous than a corrupted image?

check 4, "no image in two splits". the md5 of my planted copy matched `training/Bread/0_0.jpg`:

```
FAIL  no image in two splits
      same content in ['evaluation', 'training']: ['data\\food11_processed_mini\\training\\Bread\\0_0.jpg',
      'data\\food11_processed_mini\\evaluation\\Bread\\planted_copy.jpg']
      ... and 39 more
```

the more interesting part is the "39 more". the check was already failing before i planted anything. my real dataset has duplicates across splits, and they come from the original food-11 download, not from data.py. i checked the raw files, `training/0_106.jpg` and `evaluation/0_131.jpg` have the same md5 in `food11_raw` too.

counting them:

| dataset | evaluation images also in training | validation images also in training | duplicate groups across splits |
|---|---|---|---|
| food11_processed | 249 of 3347 (7.4%) | 51 | 611 |
| food11_processed_mini | 3 of 1096 | 2 | 43 (44 with my planted copy) |

so every test_accuracy i've logged since lab 2 on the full dataset is a bit optimistic, 7% of the test set is images the model trained on.

why the duplicate is worse: the corrupted image fails loudly. training crashes, i get a stack trace with the file name, i fix it, done. it can't silently give me a wrong number. the duplicate fails silently. everything runs, the metrics look great, and they're lying. the model gets those test images right because it memorised them, so test accuracy overestimates real accuracy, and every decision built on that number is wrong too, including the promotion gate later in this lab, which compares candidates on exactly this metric. nobody notices until the model does worse in production than it did on the test set.

---

Question 4: Your CI runner cannot see your data. Where in your workflow should `validate_data.py` run so that it still protects you? Give two places.

1. right after data preparation, as part of the data pipeline, wherever the data is. that's on my laptop after `data.py` and before `dvc add`/`dvc push`, best as a stage in `dvc.yaml` (or a git pre-commit hook that runs when `data.dvc` changes) so a new version of the data can't be committed without passing the contract.
2. at the start of training, before the first epoch. train.py (or a wrapper script) runs it on the folder it's about to train on and refuses to start if it exits non-zero. that protects the expensive step, and it means no run in mlflow was ever trained on data that broke the contract.

a third option is to make the data reachable from ci, a dvc remote in the cloud (s3, gdrive, dagshub) plus a secret for credentials, then a ci job does `dvc pull` of the mini dataset and runs the script. that's the only one where github itself enforces it.

---

Question 5: The `smoke` job has `needs: test`. What happens to it if a unit test fails? What would happen without `needs`?

with `needs: test`, if a test fails the smoke job doesn't run at all, it shows as skipped. and since push needs smoke, push is skipped too, so a broken commit never gets an image in the registry.

this happened for real on my first push (run 42007172276). the test job failed at the ruff step after 10 seconds, with exit code 2 (not a lint error, uv itself failed, `uv run` tried to re-lock and couldn't find the windows-only torch wheel `wheels/torch-2.14.0+cu132-...-win_amd64.whl` on the linux runner). the jobs api showed `test=failure; smoke=skipped; push=skipped`, and pytest inside the test job was skipped too, because steps in a job also stop at the first failure. nothing got built or pushed.

without `needs`, jobs run in parallel by default on separate runners. smoke would build and probe the image even though the tests failed. that wastes a few minutes of runner time, and worse, if push also had no needs, a commit with failing tests could still get pushed to ghcr.io. the run would be red overall, but the image would be there.

---

Question 6: How long did the whole run take? Run it a second time and compare. Which step got faster, and why?

timings from the actions api, first green run vs the empty `ci` commit right after:

| job / step | run 1 (72e6547) | run 2 (empty commit) |
|---|---|---|
| test (total) | 23s | 21s |
| &nbsp;&nbsp;uv sync --frozen | 4s | 4s |
| &nbsp;&nbsp;pytest | 13s | 11s |
| smoke (total) | 62s | 45s |
| &nbsp;&nbsp;docker build | 48s | 31s |
| push (total) | 227s | 18s |
| &nbsp;&nbsp;docker/build-push-action | **209s** | **4s** |
| **whole run** | **317s (5m17)** | **89s (1m29)** |

the step that got faster is the build and push in the push job, 209s down to 4s. that's `cache-from: type=gha` / `cache-to: type=gha,mode=max`. run 1 built every layer (installing torch cpu and the whole venv is the slow part) and saved all of them, including the intermediate builder stage, to github's actions cache. run 2 changed nothing, the commit is empty, so every layer was a cache hit, and the layers were already on ghcr.io from run 1, so all it uploaded was a new tag pointing at the same layers.

what i expected and didn't see: i thought `uv sync` would get faster thanks to `setup-uv`'s `enable-cache`. it was 4s both times, uv just downloads and installs that fast on github's network, so there wasn't much to save. the smoke job's `docker build` went 48s -> 31s, but that's not caching, it's a plain `docker build` on a brand new runner with no layer cache, so it rebuilds from scratch every time. the 17s difference is just download speed variance. if smoke ever became the slow part i'd give it the same buildx + gha cache as push.

the first ever push actually failed, see question 5, uv run re-checked the lock against pyproject.toml and needed the windows-only torch wheel in `wheels/` that isn't in git. fixed with `UV_FROZEN: "1"` in the workflow env.

---

Question 7: Why tag with the commit SHA rather than `latest`? Describe a concrete situation where `latest` leads two machines to run different code.

because a sha names exactly one build of exactly one commit and never moves. `latest` is just a pointer that every push overwrites, so it doesn't tell you what you're running.

concrete situation: monday i deploy `food11-api:latest` on server A. tuesday i merge the change from this lab that moved model loading into the startup hook, ci pushes a new `latest`. wednesday server B gets added, or server A's container gets recreated on a new host, and pulls `latest`. now A runs monday's code (docker doesn't re-pull an image it already has) and B runs tuesday's code, both claiming to be `latest`. if B behaves differently, say `/health` now reports `model_loaded` and the monitoring only works on one of them, i can't even tell which code each one is running without digging through image digests. and rolling back to "the version before" is impossible because `latest` before is gone.

with `ghcr.io/joe-haddad3/mlops-lab-1:<sha>` both servers say which commit they run, `git show <sha>` tells me exactly what's in it, and rolling back is just deploying the previous sha.

this is the code half. the model half is the `champion` alias, which is deliberately a moving pointer, but the registry keeps the version history behind it.

---

Question 8: Why does the `push` job declare `permissions:` explicitly? What could a compromised step do with a token that had write access to everything in the repo?

least privilege. `GITHUB_TOKEN` gets whatever the repo/org default permissions are, which can be write on almost everything. the push job only needs to read the code (`contents: read`) and write a package (`packages: write`), so that's all it gets. if any step misbehaves, that's the most it can do.

and every step is somebody else's code. `docker/login-action`, `docker/build-push-action`, setup-buildx, plus every python package that gets installed during the build. if one of them is compromised (a hijacked tag, a malicious release, a typosquatted dependency), it runs with my token. with full write access it could:

- push commits to main directly, for example add a backdoor to serve.py or edit ci.yml itself to steal secrets on future runs
- create/move tags and releases, so `v1.0` points to malicious code
- push a poisoned image to ghcr.io under my name that people then pull
- approve or merge pull requests, close issues, edit the wiki
- trigger other workflows that have access to real secrets

with `contents: read, packages: write` the worst case is a bad image in my package registry, which is bad but contained, and the code and history stay untouched. the token also expires when the run ends, so it can't be reused later.

---

Question 9: What does the pull request page show? Could you still merge? What does that change for a team?

i set a classic branch protection rule on `main`: require a pull request, require the `test` and `smoke` checks (no required approvals, i'm alone on the repo). then on a branch `break-category` i changed `category_from_filename` to `return CLASSES[index - 1]`, an off by one, so `0_12.jpg` comes back as Vegetable-Fruit instead of Bread, and opened pr #1.

what the pr page showed:

- "Some checks were not successful, 1 failing, 1 in progress, 2 skipped checks"
- `ci / test (push)`, **Failing after 19s**, marked **Required**
- `ci / test (pull_request)` running, also Required. the workflow has both `on: push` and `on: pull_request`, so a pr branch gets tested twice, once for the branch push and once for the merge result of the pr
- `ci / smoke (push)` and `ci / push (push)` **skipped**, because of `needs:`. smoke is Required too, so a skipped smoke counts as not passed
- the green **Merge pull request** button was greyed out
- above it a red checkbox, **"Merge without waiting for requirements to be met (bypass rules)"**

could i still merge? not normally, the button is disabled. but yes, technically, because i'm the repo owner, and admins can bypass a classic rule unless "Do not allow bypassing the above settings" is ticked. i didn't tick it, so as owner i get the escape hatch. a normal collaborator wouldn't see that checkbox at all. for a real team i'd tick "do not allow bypassing" (or use a ruleset with an empty bypass list) so the rule applies to admins too.

what it changes for a team: "everybody runs the tests on their laptop before pushing" relies on everyone remembering, every time, with the same environment. people forget, run only the tests they think are relevant, have a different python or a stale venv, or have a file on their machine that isn't committed (exactly my `wheels/` torch wheel, which made ci fail on the first push while everything passed on my laptop). with the rule:

- the check is enforced, not voluntary, and it's the same clean ubuntu machine for everybody
- the result is public on the pr, a reviewer sees red/green before reading any code, and nobody has to take "i ran the tests" on trust
- main is always green, so anyone can branch off it or deploy it, and a broken commit can't land and then get built into an image and pushed to ghcr.io, because push only runs on main

then i pushed the fix to the same branch, the checks re-ran on the new commit, went green, the merge button became available and i merged.

---

Question 10: For each candidate, what did the gate decide, and with which numbers? With your test-set size, how many accuracy points does `2 * se` represent?

first i had to fix the registry. after the `down -v` in lab 4 i re-seeded v1 by re-logging the weights, so v1's run had the model but no params and no metrics, and the champion alias was gone. the gate had nothing to compare against. i put `champion` back on v1 and copied the params and test_accuracy from the run those weights came from, gentle-koi-947 from lab 2, onto v1's run, with a tag `metrics_copied_from_run` saying where they came from.

all my lab 2 runs were on the mini dataset, so i trained both candidates on mini too (5 epochs, batch 32). otherwise they'd be scored on a different test set and comparing the accuracies would be meaningless.

| version | run | lr | test_accuracy | needs | decision |
|---|---|---|---|---|---|
| v1 | gentle-koi-947 (lab 2) | 0.0001 | 0.8248 | | champion |
| v2 | vaunted-newt-233 | 0.00001 | 0.6724 | >= 0.8478 | challenger, champion v1 kept |
| v3 | big-fawn-801 | 0.0001 | 0.8075 | >= 0.8478 | challenger, champion v1 kept |

```
--- v2 ---
champion  v1: test_accuracy=0.8248  (n=1096, se=0.0115)
candidate v2: test_accuracy=0.6724  (needs >= 0.8478)
decision: challenger (champion v1 kept)
--- v3 ---
champion  v1: test_accuracy=0.8248  (n=1096, se=0.0115)
candidate v3: test_accuracy=0.8075  (needs >= 0.8478)
decision: challenger (champion v1 kept)
```

afterwards the registry says `{'challenger': '3', 'champion': '1'}`. an alias points at one version only, so running the gate on v3 moved challenger off v2. each version also has the decision and numbers as tags (`gate_decision`, `gate_candidate_acc`, `gate_champion_acc`, `gate_threshold`, `gate_n`).

v2 is the obvious one, lr=1e-5 is just too small to get anywhere in 5 epochs. v3 is the interesting one, it's exactly the same settings as the champion, and it came out 1.7 points lower. that's just run to run noise (random init of the new head, shuffling order), and it's the whole reason the gate exists. if i'd promoted on "higher number wins" then a lucky rerun could replace the champion with a model that isn't actually better.

with my test set, n = 1096 (the mini evaluation split), p = 0.8248:

se = sqrt(0.8248 * 0.1752 / 1096) = 0.0115, so 2 * se = 0.023, about **2.3 accuracy points**. a candidate needs 0.848 or better to replace v1. on the full evaluation split (n = 3347) it would be about 1.3 points, a bigger test set gives a tighter estimate and lets the gate detect smaller real improvements.

one caveat from question 3, the mini evaluation split shares 3 images with training, so the numbers are very slightly optimistic, but the same for every candidate, so the comparison is still fair.

---

Question 11: `promote.py` needs to reach your MLflow server. Name two ways to make it run automatically after training.

1. chain it to training on the machine that can reach mlflow. at the end of train.py (or in a small `train_and_promote` script / a dvc stage after the train stage), register the new model and immediately call promote on the new version. same for a scheduled job (cron, windows task scheduler) on my laptop. simple, no cloud needed, but it only runs when my laptop runs.
2. move mlflow somewhere github can reach. dagshub gives every repo a hosted mlflow server, so i'd point `MLFLOW_TRACKING_URI` at it, store the dagshub token as a repo secret, and add a ci job (`workflow_dispatch`, or triggered after training) that runs `promote.py --version <n>`. the gate then runs in github with the decision logged in the actions history. a self-hosted runner on my laptop does the same without moving mlflow, github sends the job to my machine, and my machine can reach localhost:5000.

there's also mlflow's own model registry webhooks (on new model version created), which could trigger the ci job automatically instead of a human starting it.

---

Question 12: Draw the pipeline from `git push` to a running container. Mark which steps are automatic, which still need a human, and where the code version and the model version are decided.

```
 CODE PATH                                           MODEL PATH
 =========                                           ==========

 [human] edit code, git push branch                  [human] dvc pull / data.py
        |                                                    |
        v                                                    v
 (auto) github actions: ci.yml                       [human] validate_data.py   <- data contract
        |                                                    |
        +-- job test:  uv sync, ruff, pytest                 v
        |     | needs                                [human] train.py on GPU (laptop)
        |     v                                              |   logs params, metrics, model
        +-- job smoke: docker build, run with                v
        |     SKIP_MODEL=1, curl /health             [human] register new version in mlflow
        |                                                    |
 [human] open pr -> branch protection requires               v
         test + smoke green -> [human] merge          [human] promote.py --version n   <- quality gate
        |                                                    |   acc >= champion + 2*se ?
        v                                                    |      yes -> alias champion
 (auto) push on main                                         |      no  -> alias challenger
        |                                                    |   tags written on the version
        +-- job push: build + push                           |
              ghcr.io/joe-haddad3/mlops-lab-1:<sha>          |
                         |                                   |
   CODE VERSION DECIDED HERE                       MODEL VERSION DECIDED HERE
   (the git sha = image tag)                       (where the champion alias points)
                         |                                   |
                         v                                   v
         [human] docker pull <sha>, set image in      mlflow registry
                 compose, docker compose up                  |
                         |                                   |
                         v                                   |
                 inference container starts                  |
                 lifespan -> load_model() -----------------> models:/food11@champion
                         |
                         v
                 serving /predict
```

automatic: everything inside github actions, lint, tests, image build, smoke test, pushing the sha tagged image (on main only), and blocking the merge when checks fail.

still human: writing and merging the pr, preparing and validating the data, training (no gpu in ci), registering the model, running promote.py, and deploying, which means pulling the new image and running `docker compose up` / `restart inference` so it re-reads the champion alias (lab 4 question 8).

the two versions are decided independently. the code version is the git sha, fixed when ci builds the image. the model version is whichever version `champion` points at when the container starts. so a running container is really the pair (image sha, champion version at startup time), and changing either one is a separate release.
