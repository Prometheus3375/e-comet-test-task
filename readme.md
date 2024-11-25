A webserver to view some information about public repositories on GitHub.

# Deployment

## Preparing local environment

1. Install [Python 3.11.9](https://www.python.org/downloads/release/python-3119)
   or higher version of Python 3.11.
2. Open terminal in the root directory of this repository.
3. Initialize virtual environment inside `.venv` directory and activate it according to the
   [tutorial](https://docs.python.org/3/library/venv.html).
4. Update dependencies.
   ```
   python -m pip install -U pip setuptools wheel pip-tools
   ```
5. Generate `requirements.txt` from `requirements.in`.
   ```
   python -m piptools compile -U --strip-extras
   ```
6. Install all necessary packages.
   ```
   python -m pip install -r requirements.txt --no-deps
   ```
7. Create file `.env` from the template below and fill it accordingly.
   ```
   DATABASE_URI=<URI of PostgreSQL database>
   CONNECTION_POOL_MIN_SIZE=1
   CONNECTION_POOL_MAX_SIZE=10
   ```

## Database

Run `python create_tables.py <PostgreSQL URI>`
or execute script `create-tables.sql` for the database to create all necessary tables.

If there is no database deployed, you can deploy PostgreSQL 17 locally via Docker.

```
docker run --name postgresql -p5432:5432 -v $HOME/posgresql:/var/lib/postgresql/data -e POSTGRES_PASSWORD=mysecretpassword -d postgres:17
```

You can connect to this database via
URI `postgresql://postgres:mysecretpassword@localhost:5432/postgres`.

## Data parser

### Authentication token for GitHub

GitHub API applies heavy restrictions for non-authenticated requests.
Using an authentication token lifts rate limits significantly.
You can create personal one [here](https://github.com/settings/personal-access-tokens/new):
give name, expiration date and description, then press `Generate token`.

You can read more about GitHub API rate limits
[here](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28).

### Running locally

Run the next command to invoke the parser and update the database:

```
python -m parser --new-repo-limit 10 --new-repo-since 125266327 --github-token <GitHub token> <PostgreSQL URI>
```

Run `python -m parser --help` to view information about script arguments.

### Running on Yandex Cloud

1. Install Yandex Cloud CLI via [guide](https://yandex.cloud/en/docs/cli/quickstart).
2. Run `python -m parser.handler` to create `cloud-function.zip`.
3. Create a cloud function.
   ```bash
   yc serverless function create --name parse-github
   ```
4. Create a version for the cloud function. It parses up to 100 new repositories per run.
   ```bash
   yc serverless function version create \
     --function-name parse-github \
     --runtime python311 \
     --entrypoint parser.handler.handler \
     --memory 128m \
     --execution-timeout 600s \
     --source-path ./cloud-function.zip \
     --environment DATABASE_URI=<PostgreSQL URI>,GITHUB_TOKEN=<GitHub token>,SKIP_REPO_UPDATE=True,NEW_REPO_LIMIT=100,NEW_REPO_SINCE=125266327
   ```
5. Create a cloud trigger to invoke the function every 10 minutes.
   ```bash
   yc serverless trigger create timer \
     --name parser-period \
     --cron-expression '*/10 * ? * * *' \
     --invoke-function-id <id of parse-github function> \
     --invoke-function-service-account-id <id of service account>
   ```

Why every 10 minutes? Execution of Yandex Cloud functions is limited by 10 minutes.
The time required to parse a repository depends on the number of its commits.
During my tests the average speed was 100 commits per second,
and it was not enough to parse 150 consecutive repositories.
So I suggest 100, but 50 is a safer bet.

You can request the access to
[long-lived functions](https://yandex.cloud/en/docs/functions/concepts/long-lived-functions)
and get execution limit up to 1 hour.
In such case you can increase interval to 1 hour
and the limit of new repositories to 500-600 per run.
The interval of 1 hour is great, because GitHub API resets rate limits every hour.

Once the database is populated enough,
change environmental variables for the cloud function
to perform updates on existing repositories
and change trigger to run the function every day.

```bash
yc serverless function version create \
  --function-name parse-github \
  --runtime python311 \
  --entrypoint parser.handler.handler \
  --memory 128m \
  --execution-timeout 600s \
  --source-path ./cloud-function.zip \
  --environment DATABASE_URI=<PostgreSQL URI>,GITHUB_TOKEN=<GitHub token>,NEW_REPO_LIMIT=0
```

```bash
yc serverless trigger update timer --new-cron-expression '0 0 ? * * *'
```

Alternatively, you can create a new function and a new trigger.

Why every day? The information about activity in repositories is stored on daily basis.
Running the function with lesser intervals is not viable:

- If a repository updates rarely, fetching it again just wastes resources.
- If a repository updates often within a day,
  then its most recent activity entry is constantly rewritten.

If the time required to update the whole database exceeds execution limit,
you can create more functions and specify bounds of updating for each via environmental variables.

#### Available environmental variables

All the variables below are corresponding to options of the script for local run.
Run `python -m parser --help` to view detailed information, a brief excerpt is below.

- `DATABASE_URI` - URI of PostgreSQL. Must be set.
- `GITHUB_TOKEN` - GitHub authentication token.
- `SKIP_RANK_UPDATE` - if set to `True`, no updates are performed for previous ranks.
- `SKIP_REPO_UPDATE` - if set to `True`, no updates are performed for already present repositories.
- `UPDATE_REPO_SINCE` - the value of repository ID since which the repositories are updated.
- `UPDATE_REPO_UNTIL` - the value of repository ID until which the repositories are updated.
- `NEW_REPO_LIMIT` - the maximum number of new repositories added on each call.
- `NEW_REPO_SINCE` - new repositories are fetched after this GitHub ID.

## Web server

### Environmental variables

Before starting the server, properly configure `.env` file.
Available environmental variables are below.

- `DATABASE_URI` - URI of PostgreSQL database, must be set.
- `CONNECTION_POOL_MIN_SIZE` - the minimum size of PostgreSQL connection pool. Defaults to 1.
- `CONNECTION_POOL_MAX_SIZE` - the maximum size of PostgreSQL connection pool.
  Defaults to `None` which means the pool size is fixed to its minimum.

### Running locally

Run
```
python uvicorn api:app --env-file .env --port 2127 --log-config server/logging-config.json
```
to start the server locally.

**Note**: on Windows you must specify option `--reload`
as it runs the server with the event loop policy compatible with `psycopg`
([source](https://stackoverflow.com/q/72681045/14369408)).

### Running via Docker

Ensure that file `.env` has correct value for `DATABASE_URI`.
Then run `docker compose up` to start the server.

**Note**: If PostgreSQL is deployed locally via Docker,
then its URI provided above is not accessible from other containers.

- On Windows just replace `localhost` in the URI with `host.docker.internal`.
- General approach ([source](https://stackoverflow.com/a/70978773/14369408)):
    - Start PostgreSQL container.
    - Run `docker network create local-net`.
    - Run `docker network connect local-net <PostgreSQL container name>`.
    - Run `docker network inspect local-net`.
    - Find in the output which IPv4 is assigned to PostgreSQL container
      and replace `localhost` in the URI with this value.
    - Run `docker compose up`, wait until the server is started.
    - Run `docker network connect local-net <web server container name>`.
    - Now the server is able to connect to PostgreSQL on the next API call.
    - The container should be re-added to the network if it is recreated.
      This can be done manually or by editing `compose.yaml` as shown below.
      ```yaml
      services:
        server:
          # Present server config goes here
          # ...
          networks:
            - local-net

      networks:
        local-net:
          external: true
      ```

# Usage

After the server is deployed, open `<server_url>/docs` in browser
to view available endpoints and documentation.
To access documentation on locally deployed server, open `http://localhost:2127/docs`.
