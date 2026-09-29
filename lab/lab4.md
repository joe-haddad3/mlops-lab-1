# Lab 4 answers

note: the lab text says to move a version to "Staging", but stages are deprecated in mlflow 3.x and i already switched to aliases in lab 3, so everywhere it says Staging i used the `champion` alias instead.

also two things i had to change from the lab's mlflow/Dockerfile, both because of stuff i learned in lab 3. i used `--serve-artifacts --artifacts-destination /mlflow-data/mlartifacts` instead of `--default-artifact-root /mlflow-data/mlruns`, because default-artifact-root makes mlflow hand out filesystem paths and /mlflow-data only exists inside the mlflow container, so the inference container would get a path it can't read. and i added `--allowed-hosts "mlflow:*,..."` because mlflow 3.x blocks unknown Host headers as dns rebinding, and inference now sends `Host: mlflow:5000`. i confirmed it, curl with that header returns 200 with the flag and 403 without.

one more thing the lab doesn't mention, the volume starts empty so the containerized mlflow has no food11 model at all. my registry was in my laptop's mlflow.db. i had to seed it by loading the model off local disk and re-logging it into the container.

---

Question 1: What happens to everything written to `/mlflow-data` if you never mount a volume there and just `docker run` this image standalone?

it all disappears when the container is removed. i tested it, ran the image standalone on port 5001 with no volume, created an experiment called volume-test, confirmed it showed up, then stopped and removed the container and started a new one from the same image. the new one only had `Default`, volume-test was gone.

that's because without a mount /mlflow-data is just a folder in the container's writable layer, which is a thin read-write layer on top of the image. it belongs to that one container, not the image, so removing the container deletes it. the image is unchanged, which is why the new container comes up identical to a fresh install every time.

---

Question 2: Why a named volume here instead of a bind mount? Would a bind mount work just as well?

a bind mount would technically work, i'd see mlflow.db appear in my repo folder. but a named volume is better here for a few reasons.

it's docker managed, so i don't have to care where it actually lives, and it behaves the same on windows, mac and linux. a bind mount hardcodes a host path into docker-compose.yml, which is exactly the kind of machine specific thing that broke on me in lab 3 with the file:///C:/Users/Lenovo/... artifact paths. on windows a bind mount also goes through a filesystem translation layer into the docker vm, and sqlite locking over that is known to be flaky.

and conceptually this is server state, not source code. the stuff i want visible in my repo is the dockerfile and the compose file, not a sqlite database. i already said in lab 2 that mlflow.db shouldn't be in git, a bind mount would put it right back in my working directory.

---

Question 3: Why does `http://mlflow:5000` resolve now when `host.docker.internal` was needed before?

because compose put all three containers on a private network it created, mlops-lab-1_default, and that network has an embedded dns server that resolves every service name to that service's container ip. i checked and mlflow is 172.18.0.2, inference is .3, frontend is .4, all on 172.18.0.0/16.

in lab 3 my container was alone on the default bridge with nothing else to talk to, and mlflow was a process on my laptop outside docker entirely, so the only way in was host.docker.internal, which points back out at the host. now mlflow is a container on the same network, so it's just a neighbour i can reach by name.

the name is the service name from docker-compose.yml, not the container name. the container is actually called mlops-lab-1-mlflow-1 but `mlflow` is what resolves, which is the point, i can rename or recreate the container and the address stays the same.

---

Question 4: Why does the frontend read `INFERENCE_URL` from an environment variable?

so the image isn't tied to compose. hardcoding http://inference:8000 would mean the name `inference` has to exist, which is only true inside this specific compose network. if i docker run the frontend image on its own that name resolves to nothing and the app is dead, with no way to fix it short of editing the code and rebuilding.

with the env var the image has one sane default, http://127.0.0.1:8000, and the deployment decides the rest. compose overrides it to http://inference:8000, and on kubernetes or a different compose file it'd be something else entirely. same image, no rebuild. it's the exact same reasoning as MLFLOW_TRACKING_URI in serve.py, which is why i didn't have to touch a single line of my lab 3 code for this lab, only the value compose passes it.

---

Question 5: Why doesn't `inference` publish a port, and how does the frontend still reach it?

because publishing a port is only for traffic coming from outside docker. i need to open mlflow's ui and the streamlit page in my browser, so those two get published. nothing outside the compose network ever talks to the inference api directly, only the frontend does, and the frontend is inside the network already.

the frontend reaches it over the compose network at http://inference:8000. container to container traffic goes straight across that network and never touches the host's port space. i proved it, i execed into the frontend container and posted an image to http://inference:8000/predict and got back {"category":"Bread","confidence":0.896934986114502}, while from my windows host port 8000 isn't listening at all.

not publishing is also just better. it's less attack surface, and it avoids port collisions, i couldn't have published 8000 anyway without conflicting with things i was running before.

---

Question 6: What happens to the `inference` container if mlflow isn't ready yet?

it crashes and exits, because serve.py calls load_model at import time and there's no retry. i tested it by stopping the mlflow container and restarting inference, and inference went to `Exited (1)` with:

```
MlflowException: API request to http://mlflow:5000/api/2.0/mlflow/registered-models/alias failed with exception
HTTPConnectionPool(host='mlflow', port=5000): Max retries exceeded
(Caused by NameResolutionError("Failed to resolve 'mlflow' ([Errno -2] Name or service not known)"))
```

worth noting it's a dns failure, not connection refused. compose's embedded dns only has entries for running containers, so a stopped mlflow doesn't just refuse the connection, the name stops existing.

the honest result on a normal `docker compose up` is that it's a race and i won it, mlflow got ready before inference finished importing torch and my stack came up fine. but that's luck, not a guarantee, which is exactly the problem with depends_on. it waits for the container process to start, not for the server inside to accept connections. the proper fixes are a healthcheck on mlflow plus `depends_on: condition: service_healthy`, or a retry loop around load_model, or at minimum a restart policy so a crashed inference gets retried instead of staying dead.

---

Question 7: Run `docker compose ps`. Which services have a published port?

```
frontend    Up   0.0.0.0:8501->8501/tcp, [::]:8501->8501/tcp
inference   Up   8000/tcp
mlflow      Up   0.0.0.0:5000->5000/tcp, [::]:5000->5000/tcp
```

matches the compose file exactly. frontend and mlflow have a `ports:` block so they show the arrow form `0.0.0.0:host->container`. inference has no ports block so it just shows `8000/tcp`, which is the EXPOSE from my lab 3 Dockerfile. EXPOSE is only documentation, it says the container listens on 8000, it doesn't open anything on the host.

---

Question 8: Does the prediction come from the new version or the old one?

the old one. i registered a second version on purpose using one of my broken lr=0.01 runs from lab 2, so the two models disagree loudly, v1 says Bread on my test image and v2 says Noodles-Pasta.

i moved the champion alias to v2 and predicted again without touching the container. the registry reported champion = v2, but the api still returned {"category":"Bread","confidence":0.896934986114502}, which is v1's exact output. so the running container had no idea anything changed.

that's because serve.py calls load_model once at module import, which happens when uvicorn starts. after that the model object just sits in memory and nothing ever re-reads the alias. the command to pick up the new version is `docker compose restart inference`. after that the same container returned {"category":"Noodles-Pasta","confidence":0.9946611523628235}, so it was definitely serving v2.

---

Question 9: Why does `restart` alone work, no rebuild?

because the model isn't in the image. the image has the code and the dependencies, the venv with torch and my src folder, and that's all fixed at build time. the weights are fetched over http from the mlflow service every time the container starts, and which weights you get is decided at that moment by whatever champion points at.

so rebuilding would be pointless, nothing in the image changed. restart just kills the process and runs the entrypoint again, the import runs again, load_model resolves champion again, and this time it gets v2. that's the whole payoff of using models:/food11@champion instead of a file path, promoting a model is a registry change plus a restart, not a build and a redeploy.

the flip side is my container now has a hard startup dependency on mlflow being reachable, which is exactly what bit me in question 6.

---

Question 10: Is the model still there after down/up? What about `down -v`?

after `docker compose down` then `up`, yes, everything survived. the volume mlops-lab-1_mlflow-data was still listed after the down, and once mlflow came back the champion alias still resolved to food11 v1 READY. `down` removes containers and the network but leaves named volumes alone, and all the state lives on the volume, not in the containers.

after `docker compose down -v` it's all gone. the -v flag explicitly deletes named volumes, and the output literally says `Volume mlops-lab-1_mlflow-data Removing / Removed`. when i brought it back up docker created a brand new empty volume with the same name, mlflow initialised a fresh sqlite db, the only experiment was `Default`, and asking for the alias gave `RESOURCE_DOES_NOT_EXIST: Registered Model with name=food11 not found`. inference then couldn't start at all since there's no model to load, and i had to re-seed the registry from my local copy before the stack worked again.

so the difference is that down is about the running stack and down -v is about the data. it's the same distinction as question 1, except the volume is what usually saves you and -v is the one command that takes that safety net away.

---

Question 11: What would have to change for three replicas behind a load balancer, or for mlflow to survive a machine failure?

compose can start `deploy: replicas: 3` but that's about it, there's no load balancer, no health based routing and no rescheduling. the compose dns would round robin between the three inference containers, which isn't real load balancing, it doesn't know if one is unhealthy or overloaded. i'd need something in front, nginx or traefik, or move to an orchestrator where a service and its load balancing are built in, kubernetes with a Deployment and a Service, or docker swarm.

for replicas to actually make sense my inference service is already fine, it's stateless, it just loads a model and answers requests, so three of them are interchangeable. but they'd each download the 52mb model separately at startup and each hold their own copy in memory, and there'd be no way to make them all reload after i move the alias except restarting them one by one.

mlflow surviving a machine failure is the harder one and compose fundamentally can't do it. everything is on one box. the named volume lives on this machine's disk, so if the disk dies the registry dies with it, and my sqlite backend only supports one writer so i can't run two mlflow instances against it anyway. i'd need to split the state out, postgres for the backend store and s3 or equivalent for artifacts, both of them replicated and backed up, and then mlflow itself becomes stateless and i can run several behind a load balancer on different machines.

the general point is compose is a single host tool. it gives me one network, one set of containers and local volumes. anything about surviving a machine dying needs a cluster scheduler that can see multiple machines, reschedule work when one disappears, and storage that isn't tied to any single one of them.
