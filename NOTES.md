Package to retrieve Hyrox race data programmatically - data
\available in a S3 Bucket
API folder contains the logic for the API

This is now deployed via fly - from the command line, we can do the below useful commands

 ```
 fly auth login (required to login and run from CL) 
 fly scale count 0 (0 machines allocated to the app)
 fly machines list  (shows the state of the machine as well - so can now if running or stopped)
 fly volumes list -a pyrox-api-proud-surf-3131 (passing the application name)
 
 fly deploy (if making new changes locally and wanting to deploythe latest version)
```


Running the API via docker 
Below mounts the app/api and app/src folders to the image
So any changes are reflected without having to rebuild the container and run again!

```
docker run -it --rm -p 8000:8080 \
  -v "$PWD/api:/app/api" -v "$PWD/src:/app/src" \
  -e PYROX_BUCKET="s3://hyrox-results" -e AWS_REGION="eu-west-1" \
  pyrox-api \
  python -m uvicorn api.app:app --host 0.0.0.0 --port 8080 --reload
```

Command to build the Docker container (ran from repo root)
```
docker build -f api/Dockerfile -t pyrox-api .  
```


The API is used by the client (which is in the src folder) under the pyrox module

The base URL there is the variable that controls what we are pointing our client to (either the deployed FLY api or a Docker container running locally on port 8000)


```commandline
season6races_info = list_races(season=6)
season6racesdf = get_season(season=6, locations=['london', 'hamburg'])
london_season6 = get_race(season=6, location="london")
hamburg_season6 = get_race(season=6, location="hamburg", division="open", gender="m")
```
