> Question 1: Open the "Models" tab in the mlflow UI. What version number was your model given? What's the difference between a run's logged model artifact and a registered model?

it got version 1, since food11 didn't exist in the registry before so registering it created the model entry and made my model the first version under it.

the difference between a logged model artifact and a registered model is basically scope and identity. the logged model artifact is tied to one specific run, it's just the output that run produced, it lives under that run's artifacts and the only way to reference it is by the run id like runs:/71f4d3e5e2cb4853ba84540f6ace6491/model, which is a random hash that means nothing to anyone. every time i trained i got another one of these, my food11 experiment has 10 of them sitting there from lab 2 and half of them are from failed runs. they're just outputs, there's no notion of which one is good.

a registered model is a named thing that lives separately in the registry, food11 in my case, and versions get added under it. version 1 points at my best run's model but the name food11 doesn't care where it came from. so it's the difference between "this is what run X produced" and "this is the model we call food11". the registry entry also keeps the link back, mine still records run_id 71f4d3e5e2cb4853ba84540f6ace6491 as its source, so you don't lose the lineage, you just stop having to use it as the address.

one thing i noticed, in mlflow 3.x the logged model is already its own object with its own id, when i registered it mlflow warned me that the run had no artifacts at path 'model' and it registered based on models:/m-30c40d89cc574acba430d67b12c8f44c instead. so models aren't just files dumped in the run's artifact folder anymore, they're first class entities, and the registry is another layer of naming on top of that.

Question 2: What aliases replaced the old built-in stages in mlflow? Why version a model separately from the run that produced it, and why is an alias more flexible than a fixed stage name?

aliases aren't a fixed list, that's the point. the old system had built in stages, None, Staging, Production, Archived, and that was it, you couldn't add your own. aliases are free form names you make up, the ones everyone uses by convention are champion and challenger, i set champion on my version 1.

versioning the model separately from the run matters because the run is a record of a training job and the model is a thing you deploy, and those have different lifecycles. the run is immutable history, it happened, it has its params and metrics and that's permanent. the model version is what you actually serve, and what you serve changes. if the two were the same thing, every time you wanted to deploy a new model you'd have to go change whatever references the old run id, in my case that would mean editing serve.py and rebuilding a docker image just because i trained something better.

the alias is more flexible than a stage for a few reasons. it's a pointer you can move, so promoting version 2 is one api call that reassigns champion, no redeploy, my container just picks up the new one next time it starts. you can have as many as you want with names that mean something to your team, and you can point two aliases at the same version or move them independently, like champion on v1 while challenger sits on v3 for a shadow test. the old stages couldn't do that, there was exactly one Production slot and moving something into it forced whatever was there out. and stages were the same four words for every project regardless of whether those words described anything you were actually doing.


> Question 3: Why load the model through an mlflow model URI (`models:/food11@champion`) instead of pointing directly at the `.pth` file on disk? What would you have to change to serve a newer model version?

there isn't really a .pth to point at, train.py logged it with mlflow.pytorch.log_model so what's on disk is a whole model folder with the weights plus an MLmodel file and a signature. the signature is what makes my api safe, mlflow knows the model wants float32 [-1,3,224,224] and rejects anything else. with raw weights i'd have to rebuild the resnet18 in serve.py myself and keep it in sync with train.py forever.

the path is also machine specific and that broke on me for real. my lab 2 runs stored artifacts as file:///C:/Users/Lenovo/Desktop/... which a linux container has no way to read, i had to restart the server with --serve-artifacts and re-log the model so it got a mlflow-artifacts:/ uri it could fetch over http. models:/food11@champion works from anywhere that can reach the tracking server, and it's readable, unlike the hashes.

to serve a newer version i change nothing in my code. register the new run as version 2, move the alias with set_registered_model_alias('food11', 'champion', 2), restart the container. serve.py loads at import so it picks up v2 on startup. no code edit, no image rebuild, and if v2 is bad i point champion back at 1.


> Question 4: Why copy `pyproject.toml`/`uv.lock` and run `uv sync` *before* copying the rest of the source code, instead of copying everything at once? What happens to the build cache when you only change a line in `serve.py`?

docker caches each instruction as a layer and invalidates everything from the first changed layer onward. my uv sync layer only depends on pyproject.toml and uv.lock, so as long as those two files don't change, that layer stays cached no matter what i do to my code. that layer took 877s to build the first time, almost all of it downloading cpu torch, so it's the one i really don't want to rerun.

if i only change a line in serve.py, the COPY src/ layer invalidates and everything after it rebuilds, but that's just 45kB of files plus some ENV and EXPOSE instructions that are 0B each, so the rebuild is a couple of seconds. if i'd copied everything at once before the sync, like i did in my naive dockerfile with COPY . ., then touching serve.py would invalidate the dependency layer too and i'd be re-downloading torch every time.

> Question 5: What's the size difference between a naive single-stage image and your multi-stage one? Use `docker history <image>` to see which layers are the biggest.

my multi-stage image is 2.01GB and the naive single-stage one is 9.33GB, so 4.6x bigger, 7.32GB of waste.

from docker history the biggest layer in my real image is COPY /app/.venv at 1.44GB, then the debian base at 87.6MB and the base image's python apt layer at 48.8MB. my own code, COPY src/, is 45.1kB. so basically the entire image is torch and its dependencies, my application is a rounding error.

the extra 7.3GB in the naive one comes from a few things. it uses python:3.11 instead of python:3.11-slim so it drags in gcc and build headers, it has no --no-dev so dev dependencies get installed, and most of all uv's download cache stays in the final layer instead of being thrown away with the builder stage. on top of that COPY . . pulled my 1.9GB wheels folder straight into the image. that's the point of multi-stage, the builder stage can be as messy as it wants because only the .venv gets copied out of it.

> Question 6: What happens to build speed and image size if you forget the `.dockerignore`? Which of the excluded folders would actually break the build if they were sent to the Docker daemon?


without .dockerignore docker packages the whole directory and ships it to the daemon before running a single instruction. my project is 8.1GB, and just running du on it took over 2 minutes, so every build would start with that upload. i saw the real effect in my two builds, my multi-stage one transferred 200.83kB of context while the naive one transferred 1.99GB, same ignore file, the difference is that buildkit only sends what the COPY instructions actually need and COPY . . needs everything.

for image size it depends on whether you COPY . . or not. if you do, everything lands in the image, which is exactly how my naive build ended up with my 1.9GB wheels folder baked in for no reason.

the one that would actually break the build is .venv. it's 3.5GB of windows binaries and .pyd files, and if it got copied into a linux image over the venv i just built, nothing would import. data/ and .dvc/ wouldn't break anything, they'd just make the build slow and the image huge, 1.3GB each in my case.

> Question 7: Why can't the container simply use `127.0.0.1:5000` to reach the mlflow server on your host? What does `host.docker.internal` resolve to?

because 127.0.0.1 inside the container is the container's own loopback, not mine. every container gets its own network namespace, so localhost means "this container" and nothing is listening on port 5000 in there, the connection just gets refused. it's the same confusion i hit when i typed 0.0.0.0:5000 into chrome and got ERR_ADDRESS_INVALID, an address only means something relative to who's asking.

host.docker.internal is a dns name docker desktop injects into the container that resolves to the host machine's address on the virtual network docker sets up. it exists on mac and windows because the containers actually run inside a vm, on linux you'd use --network host instead.

two things had to be right for this to work for me. the mlflow server had to be started with --host 0.0.0.0 so it listens on all interfaces instead of just loopback, otherwise the container's request never gets accepted. and mlflow 3.x has dns rebinding protection that checks the Host header against an allowlist of localhost and private ips, so host.docker.internal:5000 got rejected with a 403 until i restarted the server with --allowed-hosts "host.docker.internal:,localhost:,localhost,127.0.0.1:*,127.0.0.1".

> Question 8: Stop the container and start a new one from the same image. Does the model still load correctly without you rebuilding? What does that tell you about what's baked into the image versus fetched at runtime?

yes, it loads fine. i stopped the container and ran a new one from the same image and it came up with no rebuild, same short pause then Uvicorn running on http://0.0.0.0:8000, and predictions worked right away.

what that tells me is the image contains the code and the dependencies, the venv with torch and the src folder, and that's it. the weights are not in there, they get pulled from the mlflow registry over http at startup, every time the container starts. my serve.py calls load_model at module level so it happens once during import and then stays in memory.

that split is the whole point. the image is immutable and only changes when i rebuild, but the model it serves is decided at runtime by whatever version champion points at. if i register a version 2 and move the alias, the same image restarted serves the new model with no rebuild. the tradeoff is the container now has a startup dependency on the tracking server being reachable, if mlflow is down my container won't start at all.

> Question 9: The Dockerfile and image are versioned differently — one lives in git, the other doesn't (yet). What's still missing before another machine (like a CI runner or a Kubernetes cluster) could reliably pull and run the exact image you just built?

the dockerfile is in git so anyone can rebuild, but a rebuild isn't the same image. the missing pieces are:

the image isn't in a registry. it only exists in my local docker daemon, so a ci runner or a kubernetes node has nothing to pull. it needs to be pushed somewhere like docker hub or ghcr.

the tag isn't immutable. food11-api:latest is a moving pointer, i can overwrite it tomorrow and anything pulling latest gets something different. for reproducibility you pull by digest, my image is sha256:404fd42916be..., which is content addressed and can never mean anything else.

the tracking server isn't reachable. host.docker.internal is my laptop, that name means nothing on a cluster. mlflow would need a real address, and the artifacts would need to live somewhere shared like s3 instead of my local mlartifacts folder.

there's also no build automation, right now the image only exists because i ran docker build by hand, so nothing guarantees the image in the registry actually matches the commit it claims to come from.